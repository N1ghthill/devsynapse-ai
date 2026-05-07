"""Skill templates for DevSynapse AI."""
from __future__ import annotations

from typing import Any

SKILL_TEMPLATES: dict[str, dict[str, Any]] = {
    "python-dev": {
        "name": "Python Development",
        "description": "Best practices for Python development",
        "category": "programming",
        "tags": ["python", "best-practices", "pep8"],
        "body": """# Python Development Best Practices

## Code Style
- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for modules, classes, and functions
- Keep functions small and focused

## Testing
- Write tests with pytest
- Aim for high test coverage
- Use fixtures for common setup
- Mock external dependencies

## Project Structure
```
project/
├── src/
│   └── package/
│       ├── __init__.py
│       ├── module.py
│       └── tests/
│           └── test_module.py
├── pyproject.toml
├── README.md
└── requirements.txt
```

## Dependencies
- Use pyproject.toml for dependency management
- Pin versions in requirements.lock
- Use virtual environments
""",
    },
    "rust-dev": {
        "name": "Rust Development",
        "description": "Best practices for Rust development",
        "category": "programming",
        "tags": ["rust", "best-practices", "cargo"],
        "body": """# Rust Development Best Practices

## Code Style
- Follow Rust style guidelines
- Use `cargo fmt` for formatting
- Use `cargo clippy` for linting
- Prefer `Result` over `Option` for errors

## Error Handling
- Use `thiserror` for custom errors
- Use `anyhow` for application errors
- Propagate errors with `?` operator
- Provide context with `.context()`

## Project Structure
```
project/
├── src/
│   ├── main.rs
│   ├── lib.rs
│   └── modules/
├── Cargo.toml
├── tests/
└── benches/
```

## Testing
- Write unit tests with `#[cfg(test)]`
- Write integration tests in `tests/`
- Use `cargo test` for running tests
- Benchmark with `cargo bench`
""",
    },
    "web-frontend": {
        "name": "Web Frontend Development",
        "description": "Best practices for web frontend development",
        "category": "programming",
        "tags": ["javascript", "typescript", "react", "frontend"],
        "body": """# Web Frontend Development Best Practices

## Code Style
- Use TypeScript for type safety
- Follow ESLint and Prettier configurations
- Use functional components with hooks
- Keep components small and focused

## Project Structure
```
project/
├── src/
│   ├── components/
│   ├── hooks/
│   ├── utils/
│   ├── types/
│   ├── App.tsx
│   └── index.tsx
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Testing
- Write unit tests with Jest/Vitest
- Write integration tests with React Testing Library
- Use mock data for API responses
- Test user interactions

## Performance
- Use React.memo for expensive components
- Lazy load routes with React.lazy
- Optimize images and assets
- Use code splitting
""",
    },
    "api-design": {
        "name": "API Design",
        "description": "Best practices for REST API design",
        "category": "architecture",
        "tags": ["api", "rest", "design", "backend"],
        "body": """# API Design Best Practices

## REST Principles
- Use nouns for resources (e.g., `/users`, not `/getUsers`)
- Use HTTP methods correctly (GET, POST, PUT, DELETE)
- Use plural nouns for collections
- Version your API (e.g., `/api/v1/users`)

## Response Format
```json
{
  "data": {...},
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  },
  "links": {
    "self": "/api/v1/users?page=1",
    "next": "/api/v1/users?page=2"
  }
}
```

## Error Handling
- Use appropriate HTTP status codes
- Return consistent error format
- Include error details and suggestions
- Log errors server-side

## Security
- Use HTTPS
- Implement authentication and authorization
- Validate all inputs
- Rate limit endpoints
""",
    },
    "git-workflow": {
        "name": "Git Workflow",
        "description": "Best practices for Git version control",
        "category": "workflow",
        "tags": ["git", "version-control", "workflow"],
        "body": """# Git Workflow Best Practices

## Branch Strategy
- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Urgent production fixes

## Commit Messages
```
type: subject

body (optional)

footer (optional)
```

Types: feat, fix, docs, style, refactor, test, chore

## Commands
```bash
# Create feature branch
git checkout -b feature/my-feature

# Commit changes
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/my-feature
```

## Best Practices
- Commit often with clear messages
- Rebase before merging
- Resolve conflicts early
- Keep main branch stable
""",
    },
}
