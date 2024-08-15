# Tesseract : Concurrent Blockchain Transaction Buffer

This project implements a system for buffering and managing concurrent transactions across different rollups in a blockchain environment. It consists of a smart contract written in Vyper and a Python script for interacting with the contract.

## Smart Contract (Vyper)

The smart contract (`ConcurrentTransactionBuffer.vy`) provides the following functionality:

- Buffering transactions with dependencies and timestamps
- Resolving dependencies for buffered transactions
- Checking if a transaction is ready for execution

### Key Functions:

1. `buffer_transaction`: Stores a new transaction with its details.
2. `resolve_dependency`: Marks a transaction as ready when its dependency is resolved.
3. `is_transaction_ready`: Checks if a transaction is ready for execution.

## Python Interaction Script

The Python script (`interact_with_contract.py`) demonstrates how to interact with the smart contract using Web3.py. It includes functions for:

- Buffering a transaction
- Resolving concurrency between two transactions

## Setup and Usage

1. Deploy the Vyper contract to your chosen Ethereum network.
2. Update the `contract_address` and `contract_abi` in the Python script with your deployed contract's details.
3. Ensure you have Web3.py installed: `pip install web3`
4. Run the Python script to interact with the contract.

## Requirements

- Vyper (for smart contract compilation)
- Web3.py
- An Ethereum node or provider (e.g., Infura)

## Important Notes

- Ensure proper private key management when using the Python script.
- The current implementation uses a 30-second window for concurrent transactions. Adjust as needed for your use case.
- This system is designed for cross-rollup transaction management. Ensure your rollup infrastructure is compatible.

## Future Improvements

- Implement a more sophisticated concurrency resolution mechanism.
- Add events for better off-chain tracking of transaction states.
- Enhance error handling and input validation.

## License

This project is licensed under the MIT License:

MIT License

Copyright (c) 2024 [Your Name or Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contributing

We welcome contributions to the Concurrent Transaction Buffer project! Here are some ways you can contribute:

1. Report bugs or suggest features by opening an issue.
2. Improve documentation, including this README and code comments.
3. Submit pull requests with bug fixes or new features.

To contribute code:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes, ensuring they adhere to the project's coding style.
4. Write or update tests as necessary.
5. Submit a pull request with a clear description of your changes.

Please ensure your code follows the existing style and includes appropriate tests. By contributing, you agree that your contributions will be licensed under the project's MIT License.
