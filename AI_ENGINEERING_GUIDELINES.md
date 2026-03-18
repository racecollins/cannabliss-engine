# AI Engineering Guidelines

Feature requirements:
- Implement this as an isolated, loosely coupled module where possible.
- Keep feature-specific logic contained to a small number of clearly scoped files.
- The feature may depend on core services, but core services should not depend on this feature.
- Prefer clear interfaces, centralized types, and readable code over cleverness.
- Avoid unrelated refactors.
- Add or update lightweight verification so the change can be validated easily.
- Keep the implementation easy to modify or remove later.
