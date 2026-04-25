"""
Sistema de monitoramento do DevSynapse
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import MONITORING_DB_PATH
from core.migrations import build_monitoring_migration_manager

logger = logging.getLogger(__name__)


class MonitoringSystem:
    """Sistema de monitoramento e métricas"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or MONITORING_DB_PATH
        self._init_database()
        
    def _init_database(self):
        """Inicializa banco de dados de monitoramento"""

        build_monitoring_migration_manager(self.db_path).apply_migrations()

        conn = sqlite3.connect(self.db_path)
        conn.commit()
        conn.close()
        
        logger.info(f"Sistema de monitoramento inicializado: {self.db_path}")
    
    def log_command_execution(
        self,
        command_type: str,
        command_text: str,
        success: bool,
        execution_time: float,
        user_id: Optional[str] = None,
        project_name: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Registra execução de um comando"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO command_executions 
            (timestamp, command_type, command_text, success, execution_time, user_id, project_name, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            command_type,
            command_text[:500],  # Limitar tamanho
            int(success),
            execution_time,
            user_id,
            project_name,
            error_message[:1000] if error_message else None
        ))
        
        conn.commit()
        conn.close()
        
        # Verificar se precisa gerar alerta
        if not success and error_message:
            self.create_alert(
                alert_type="command_failure",
                severity="warning",
                message=f"Falha no comando {command_type}: {error_message[:200]}"
            )
    
    def log_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Registra requisição à API"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_usage 
            (timestamp, endpoint, method, status_code, response_time, user_id, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            endpoint,
            method,
            status_code,
            response_time,
            user_id,
            ip_address
        ))
        
        conn.commit()
        conn.close()
        
        # Alertas para erros HTTP
        if status_code >= 500:
            self.create_alert(
                alert_type="server_error",
                severity="critical",
                message=f"Erro {status_code} em {endpoint}"
            )
        elif status_code >= 400:
            self.create_alert(
                alert_type="client_error",
                severity="warning",
                message=f"Erro {status_code} em {endpoint}"
            )
    
    def log_system_metric(
        self,
        metric_name: str,
        metric_value: float,
        tags: Optional[Dict] = None
    ):
        """Registra métrica do sistema"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags) if tags else None
        
        cursor.execute('''
            INSERT INTO system_metrics 
            (timestamp, metric_name, metric_value, tags)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            metric_name,
            metric_value,
            tags_json
        ))
        
        conn.commit()
        conn.close()
    
    def create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str
    ):
        """Cria um alerta"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alerts 
            (timestamp, alert_type, severity, message)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            alert_type,
            severity,
            message[:1000]
        ))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"ALERTA [{severity.upper()}]: {message}")
    
    def resolve_alert(self, alert_id: int):
        """Marca um alerta como resolvido"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE alerts 
            SET resolved = 1, resolved_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), alert_id))
        
        conn.commit()
        conn.close()

    def sync_llm_budget_alerts(self, budget_status: Dict):
        """Create or resolve budget alerts based on current LLM spend."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        def resolve_window_alerts(window: str):
            cursor.execute(
                '''
                UPDATE alerts
                SET resolved = 1, resolved_at = ?
                WHERE resolved = 0 AND alert_type = ?
                ''',
                (datetime.now().isoformat(), f"llm_budget_{window}"),
            )

        def upsert_window_alert(window: str, severity: str, message: str):
            alert_type = f"llm_budget_{window}"

            cursor.execute(
                '''
                SELECT id, severity, message
                FROM alerts
                WHERE resolved = 0 AND alert_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
                ''',
                (alert_type,),
            )
            current = cursor.fetchone()

            if current and current["severity"] == severity and current["message"] == message:
                return

            cursor.execute(
                '''
                UPDATE alerts
                SET resolved = 1, resolved_at = ?
                WHERE resolved = 0 AND alert_type = ?
                ''',
                (datetime.now().isoformat(), alert_type),
            )
            cursor.execute(
                '''
                INSERT INTO alerts (timestamp, alert_type, severity, message)
                VALUES (?, ?, ?, ?)
                ''',
                (datetime.now().isoformat(), alert_type, severity, message[:1000]),
            )

        for window in ("daily", "monthly"):
            snapshot = budget_status.get(window, {})
            level = snapshot.get("level", "disabled")
            budget_usd = float(snapshot.get("budget_usd") or 0.0)
            actual_cost_usd = float(snapshot.get("actual_cost_usd") or 0.0)
            usage_pct = float(snapshot.get("usage_pct") or 0.0)

            if level in {"disabled", "healthy"} or budget_usd <= 0:
                resolve_window_alerts(window)
                continue

            severity = "critical" if level == "critical" else "warning"
            message = (
                f"LLM {window} budget at {usage_pct:.1f}% "
                f"(${actual_cost_usd:.6f} / ${budget_usd:.6f})."
            )
            upsert_window_alert(window, severity, message)

        conn.commit()
        conn.close()
    
    def get_command_stats(self, hours: int = 24) -> Dict:
        """Obtém estatísticas de comandos"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Total de comandos
        cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
            FROM command_executions
            WHERE timestamp >= ?
        ''', (since_time,))
        
        totals = cursor.fetchone()
        
        # Comandos por tipo
        cursor.execute('''
            SELECT command_type,
                   COUNT(*) as count,
                   AVG(execution_time) as avg_time,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM command_executions
            WHERE timestamp >= ?
            GROUP BY command_type
            ORDER BY count DESC
        ''', (since_time,))
        
        by_type = [dict(row) for row in cursor.fetchall()]
        
        # Comandos recentes
        cursor.execute('''
            SELECT timestamp, command_type, command_text, success, execution_time
            FROM command_executions
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (since_time,))
        
        recent = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "totals": dict(totals),
            "by_type": by_type,
            "recent": recent,
            "timeframe_hours": hours
        }
    
    def get_api_stats(self, hours: int = 24) -> Dict:
        """Obtém estatísticas da API"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Total de requisições
        cursor.execute('''
            SELECT COUNT(*) as total_requests,
                   AVG(response_time) as avg_response_time,
                   COUNT(DISTINCT endpoint) as unique_endpoints
            FROM api_usage
            WHERE timestamp >= ?
        ''', (since_time,))
        
        totals = cursor.fetchone()
        
        # Requisições por endpoint
        cursor.execute('''
            SELECT endpoint, method,
                   COUNT(*) as request_count,
                   AVG(response_time) as avg_response_time,
                   SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
            FROM api_usage
            WHERE timestamp >= ?
            GROUP BY endpoint, method
            ORDER BY request_count DESC
        ''', (since_time,))
        
        by_endpoint = [dict(row) for row in cursor.fetchall()]
        
        # Códigos de status
        cursor.execute('''
            SELECT status_code,
                   COUNT(*) as count
            FROM api_usage
            WHERE timestamp >= ?
            GROUP BY status_code
            ORDER BY count DESC
        ''', (since_time,))
        
        status_codes = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "totals": dict(totals),
            "by_endpoint": by_endpoint,
            "status_codes": status_codes,
            "timeframe_hours": hours
        }
    
    def get_active_alerts(self) -> List[Dict]:
        """Obtém alertas ativos"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, timestamp, alert_type, severity, message
            FROM alerts
            WHERE resolved = 0
            ORDER BY 
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'warning' THEN 2
                    WHEN 'info' THEN 3
                    ELSE 4
                END,
                timestamp DESC
        ''')
        
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return alerts
    
    def get_system_health(self) -> Dict:
        """Obtém saúde geral do sistema"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Última hora
        hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        # Taxa de erro de comandos (última hora)
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
            FROM command_executions
            WHERE timestamp >= ?
        ''', (hour_ago,))
        
        cmd_stats = cursor.fetchone()
        cmd_error_rate = cmd_stats[1] / cmd_stats[0] if cmd_stats[0] > 0 else 0
        
        # Taxa de erro da API (última hora)
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
            FROM api_usage
            WHERE timestamp >= ?
        ''', (hour_ago,))
        
        api_stats = cursor.fetchone()
        api_error_rate = api_stats[1] / api_stats[0] if api_stats[0] > 0 else 0
        
        # Alertas ativos
        cursor.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0')
        active_alerts = cursor.fetchone()[0]
        
        # Alertas críticos
        cursor.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0 AND severity = "critical"')
        critical_alerts = cursor.fetchone()[0]
        
        conn.close()
        
        # Determinar status geral
        if critical_alerts > 0:
            overall_status = "critical"
        elif active_alerts > 0:
            overall_status = "warning"
        elif cmd_error_rate > 0.1 or api_error_rate > 0.1:  # 10% de erro
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            "overall_status": overall_status,
            "command_error_rate": cmd_error_rate,
            "api_error_rate": api_error_rate,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "last_updated": datetime.now().isoformat()
        }


# Instância global
monitoring_system = MonitoringSystem()
