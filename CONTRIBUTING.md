# Contributing to Tesseract

We welcome contributions to the Tesseract cross-rollup transaction coordination protocol. This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry for dependency management
- Git for version control
- Basic understanding of blockchain and smart contracts

### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/your-username/tesseract.git
   cd tesseract
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```

3. **Verify installation**
   ```bash
   poetry run python scripts/test_compilation.py
   ```

## Development Guidelines

### Code Standards

- **Vyper Contracts**: Follow the [Vyper Style Guide](https://vyper.readthedocs.io/en/stable/style-guide.html)
- **Python Code**: Use [Black](https://black.readthedocs.io/) for formatting
- **Documentation**: Add comprehensive docstrings for all functions
- **Testing**: Include unit tests for all new functionality

### Commit Messages

Use clear, descriptive commit messages:
- `feat: add cross-chain dependency resolution`
- `fix: resolve gas estimation issue in deployment`
- `docs: update API documentation for new functions`
- `test: add unit tests for transaction buffering`

### Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/descriptive-name
   ```

2. **Make your changes**
   - Follow coding standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   poetry run python scripts/test_compilation.py
   # Add additional tests as needed
   ```

4. **Submit pull request**
   - Provide clear description of changes
   - Reference any related issues
   - Ensure all tests pass

## Types of Contributions

### Smart Contract Development
- Bug fixes in Vyper contracts
- Gas optimization improvements
- Security enhancements
- New cross-rollup features

### Infrastructure
- Deployment script improvements
- Testing framework enhancements
- Monitoring and logging tools
- Documentation improvements

### Documentation
- API documentation updates
- Tutorial and guide creation
- Code example improvements
- Architecture documentation

## Testing

### Contract Testing
```bash
# Test contract compilation
poetry run python scripts/test_compilation.py

# Test basic functionality
poetry run python scripts/test_basic.py
```

### Integration Testing
- Test cross-rollup functionality
- Validate deployment scripts
- Verify gas estimations

## Security

### Reporting Security Issues
- **Do not** open public issues for security vulnerabilities
- Email security@tesseract.io with details
- We will respond within 48 hours

### Security Guidelines
- Never commit private keys or sensitive data
- Follow secure coding practices
- Validate all user inputs
- Use established security patterns

## Code Review

All submissions require code review. We use GitHub pull requests for this purpose. Reviewers will check:

- Code quality and standards compliance
- Test coverage and functionality
- Documentation completeness
- Security considerations

## Community Guidelines

### Be Respectful
- Use inclusive language
- Be constructive in feedback
- Help others learn and grow

### Stay Focused
- Keep discussions on-topic
- Use appropriate channels for different types of discussions
- Respect maintainer time and priorities

## Getting Help

- **Documentation**: Check [docs/](docs/) for comprehensive guides
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Discord**: Join our community Discord for real-time help

## License

By contributing to Tesseract, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors will be recognized in:
- Release notes for significant contributions
- Project documentation
- Annual contributor recognition

Thank you for contributing to Tesseract!