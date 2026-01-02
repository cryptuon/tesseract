# Contributing

Thank you for your interest in contributing to Tesseract!

---

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry
- Git
- Basic understanding of Vyper and smart contracts

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/tesseract.git
cd tesseract

# Install dependencies
poetry install --with dev

# Activate environment
poetry shell

# Verify setup
poetry run python scripts/test_compilation.py
```

---

## Development Workflow

### 1. Create a Branch

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Or bugfix branch
git checkout -b fix/issue-description
```

### 2. Make Changes

- Follow the coding standards below
- Write tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run compilation test
poetry run python scripts/test_compilation.py

# Run test suite
poetry run pytest tests/ -v

# Format code
poetry run black .
```

### 4. Submit Pull Request

```bash
# Commit changes
git add .
git commit -m "feat: add new feature description"

# Push branch
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Coding Standards

### Vyper Contracts

Follow the [Vyper Style Guide](https://vyper.readthedocs.io/en/stable/style-guide.html):

```vyper
# Good: Clear, explicit code
@external
def buffer_transaction(tx_id: bytes32, origin: address, target: address):
    assert self.authorized_operators[msg.sender], "Not authorized"
    assert tx_id != empty(bytes32), "Invalid transaction ID"
    # ...

# Bad: Unclear, implicit behavior
@external
def buffer(t: bytes32, o: address, ta: address):
    if self.auth[msg.sender]:
        # ...
```

### Python Code

- Use [Black](https://black.readthedocs.io/) for formatting
- Follow PEP 8 guidelines
- Add type hints where helpful

```python
# Good
def buffer_transaction(
    tx_id: bytes,
    origin: str,
    target: str,
    payload: bytes
) -> dict:
    """Buffer a cross-rollup transaction.

    Args:
        tx_id: Unique transaction identifier
        origin: Origin rollup address
        target: Target rollup address
        payload: Transaction data

    Returns:
        Transaction receipt
    """
    ...

# Bad
def buffer(t, o, ta, p):
    ...
```

---

## Pull Request Guidelines

### Title Format

Use conventional commits format:

- `feat: Add new feature`
- `fix: Fix bug in X`
- `docs: Update documentation`
- `test: Add tests for Y`
- `refactor: Refactor Z component`

### Description Template

```markdown
## Summary
Brief description of changes

## Changes
- Change 1
- Change 2

## Testing
How to test these changes

## Related Issues
Fixes #123
```

### Review Process

1. All tests must pass
2. Code must be formatted with Black
3. Documentation updated if needed
4. At least one approval required

---

## Testing Guidelines

### Writing Tests

```python
import pytest
from tesseract import TesseractClient

class TestBufferTransaction:
    """Tests for buffer_transaction function."""

    def test_buffer_valid_transaction(self, contract, operator):
        """Test buffering a valid transaction."""
        tx_id = b'\x01' * 32

        result = contract.functions.buffer_transaction(
            tx_id,
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            b"test payload",
            b'\x00' * 32,
            int(time.time()) + 60
        ).transact({'from': operator})

        state = contract.functions.get_transaction_state(tx_id).call()
        assert state == 1  # BUFFERED

    def test_buffer_rejects_invalid_id(self, contract, operator):
        """Test that empty transaction ID is rejected."""
        with pytest.raises(Exception) as exc:
            contract.functions.buffer_transaction(
                b'\x00' * 32,  # Empty ID
                ...
            ).transact({'from': operator})

        assert "Invalid transaction ID" in str(exc.value)
```

### Test Coverage

Aim for high coverage on:

- All public functions
- Edge cases and error conditions
- State transitions
- Access control

---

## Documentation

### Code Comments

```vyper
# Use comments to explain WHY, not WHAT
# Good: Limit payload size to prevent gas griefing
payload: Bytes[512]

# Bad: Define payload as 512 bytes
payload: Bytes[512]
```

### Documentation Files

- Update relevant docs when changing functionality
- Add examples for new features
- Keep API reference in sync

---

## Issue Reporting

### Bug Reports

Include:

- Tesseract version
- Python version
- Network (mainnet/testnet)
- Steps to reproduce
- Expected vs actual behavior
- Error messages

### Feature Requests

Include:

- Use case description
- Proposed solution
- Alternative approaches considered

---

## Security

### Reporting Vulnerabilities

**Do NOT open public issues for security vulnerabilities.**

Email security@tesseract-protocol.io with:

- Description of vulnerability
- Steps to reproduce
- Potential impact

### Security Considerations

When contributing:

- Review for common vulnerabilities (reentrancy, overflow, etc.)
- Test access control thoroughly
- Consider gas costs and DoS vectors
- Don't introduce external dependencies lightly

---

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and ideas
- **Discord**: Real-time chat
- **Twitter**: Updates and announcements

### Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow project guidelines

---

## Recognition

Contributors are recognized in:

- GitHub contributors list
- Release notes
- Project documentation

Thank you for helping make Tesseract better!
