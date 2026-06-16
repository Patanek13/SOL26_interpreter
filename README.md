# SOL26 Interpreter & Integration Testing Framework

A fully functional, strictly typed interpreter for **SOL26** (a pure object-oriented, Smalltalk-inspired programming language) along with a robust End-to-End (E2E) Integration Testing tool.

This project was built to demonstrate deep knowledge of **Object-Oriented Programming (OOP) paradigms, AST (Abstract Syntax Tree) evaluation, lexical scoping (closures), and cross-language system integration**.

## Key Technical Highlights

### 1. The SOL26 Interpreter (Python)

Architected a dynamic interpreter that evaluates XML-represented Abstract Syntax Trees (AST).

* **Pure OOP Architecture:** Everything in the language is an object, including basic types (Integer, String) and execution blocks.
* **Lexical Scoping & Closures:** Engineered a robust `LocalFrame` memory management system with parent-referencing chains to properly handle nested blocks, closures, and variable shadowing.
* **Dynamic Dispatch & Built-ins:** Implemented dynamic method resolution traversing class hierarchies, with seamless fallback mechanisms for instance attributes and singleton design patterns (True, False, Nil).
* **Two-Phase Initialization:** Designed a safe, two-phase program loading sequence to accurately detect cyclic inheritance without risking infinite loops or memory leaks.

### 2. Integration Testing Framework (TypeScript / Node.js)

Developed a standalone CLI testing framework from scratch to validate the interpreter against complex test cases.

* **Subprocess Management:** Automated the orchestration of parser and interpreter processes, securely passing standard inputs (I/O) and capturing output streams (`stdout`, `stderr`).
* **Smart Output Verification:** Implemented logic to intelligently compare output using GNU `diff`, with smart skipping mechanisms for expected non-zero exit codes.
* **Advanced Filtering & Reporting:** Built a CLI parser supporting regex-based inclusion/exclusion filters and detailed JSON report generation.

### 3. CI/CD & DevSecOps Practices

* **Containerization:** Built a multi-stage `Dockerfile` ensuring clean separation of build, linting, and runtime environments. Overcame cross-environment Python/Node.js binary incompatibilities.
* **Zero-Warning Policy:** The entire codebase enforces strict static analysis:
  * **Python:** Checked strictly by `Mypy` and formatted/linted by `Ruff`.
  * **TypeScript:** Strictly typed and linted by `ESLint` & `Prettier`.

## Engineering Challenges Overcome

To give an insight into my problem-solving process, here are a few complex challenges resolved during development:

1. **Closure Memory Leaks & Lexical Scoping:**
   * *Problem:* Early versions failed to retain outer-scope variable references when executing nested blocks (closures).
   * *Solution:* Designed a linked-list-like `LocalFrame` class. When reading or assigning a variable, the interpreter recursively climbs the frame hierarchy, ensuring perfect variable state retention and preventing parameter collisions.

2. **Strict Type Safety in Dynamic ASTs:**
   * *Problem:* Using Python's `mypy` on dynamically loaded trees caused massive type-checking errors.
   * *Solution:* Adopted extensive defensive programming strategies, explicit type guarding, and short-circuit evaluation, achieving a 100% type-safe codebase without suppressing a single warning.

3. **Subprocess I/O Deadlocks:**
   * *Problem:* Node.js standard UNIX piping (`.pipe`) caused deadlocks when the Python script dynamically evaluated stream requirements.
   * *Solution:* Refactored the inter-process communication (IPC) to pass file buffers explicitly via CLI arguments (`--input`), drastically improving testing stability.

## Project Evaluation Results

The project was subjected to a rigorous, automated academic evaluation pipeline testing edge cases, algorithmic stability, and code quality. It achieved outstanding results:

* **E2E Interpreter Robustness (6.99 / 7.70):** Achieved an exceptional score (over 90%) across hundreds of aggressive execution tests. Reached **100% success rate** in the most advanced categories, including:
  * *Lexical Closures & Scoping*
  * *Complex End-to-End Programs* (e.g., iterative/recursive algorithms)
  * *Block Semantics & Arity validation*
  * *Bonus Language Extensions*
* **Integration Testing Framework (17 / 17):** Passed 100% of the complex evaluation scenarios, proving flawless parsing, filtering, process execution, and differential analysis.
* **Code Quality Assurance:** Achieved a flawless **0 Errors / 0 Warnings** across the entire multi-language codebase (enforced by `Mypy`, `Ruff`, `ESLint`, and `Prettier` strict modes).

## Tech Stack & Architecture

| Component | Technology | Description | 
| ----- | ----- | ----- | 
| **Interpreter** | Python 3.14 | Core evaluation engine, OOP logic, AST parsing via `lxml` and `pydantic`. | 
| **Tester** | TypeScript / Node.js | E2E CLI tool, file-system operations, process spawning, JSON reporting. | 
| **Tooling** | Docker, Ruff, Mypy, ESLint | Multi-stage container builds and strict static code analysis. | 

## Getting Started

### Prerequisites

Make sure you have [Docker](https://www.docker.com/) or [Podman](https://podman.io/) installed.

### Build the Environment

The project is fully containerized. You can build the necessary stages directly from the `Dockerfile`:

```bash
# Build the production-ready interpreter image
docker build --target runtime -t sol26-interpreter .

# Build the testing framework image
docker build --target test -t sol26-tester .

### Running the Interpreter

```bash
docker run --rm -v $(pwd):/app/data sol26-interpreter --source /app/data/program.xml --input /app/data/input.in

### Running the E2E Tester

The tester accepts various flags for recursive searching (-r), regex filtering (-ic, -it), and output file generation (-o).

```bash
docker run --rm -v $(pwd)/test_suite:/opt/tests sol26-tester -r -o /opt/tests/report.json /opt/tests

*Note: This project was developed as part of an advanced university course focusing on Principles of Programming Languages and OOP (IPP).*
