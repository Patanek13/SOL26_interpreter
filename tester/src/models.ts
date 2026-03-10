/**
 * This module defines the data models used for representing test cases and their results.
 * It serves as the reference for the testing tool's expected output data structure.
 *
 * Author: Ondřej Ondryáš <iondryas@fit.vut.cz>
 *
 * AI usage notice: The author used OpenAI Codex to create the implementation of this
 *                  module based on its Python counterpart.
 */

// ---- Test cases ----

export enum TestCaseType {
  /** Represents the type of a test case: SOL2XML, interpretation only, combined. */
  PARSE_ONLY = 0,
  EXECUTE_ONLY = 1,
  COMBINED = 2,
}

export interface TestCaseDefinitionFileInit {
  name: string;
  test_source_path: string;
  stdin_file?: string | null;
  expected_stdout_file?: string | null;
}

export class TestCaseDefinitionFile {
  /**
   * Represents a single discovered test case file.
   *
   * IPP: This model may (or may not) be useful for your internal processing, or you may
   *      choose to create your own internal models and only in the end create the final
   *      TestCaseDefinition instances to include in the output report.
   *
   *      Do not modify this model directly, as it is used as the parent of the
   *      TestCaseDefinition model, which is included in the output report.
   */

  /** The test case name, derived from the test case file name without the '.test' extension. */
  public readonly name: string;
  /** Path to the test case definition file ('.test'). */
  public readonly test_source_path: string;
  /**
   * Path to a file with the standard input contents for the interpreter.
   * Present if the '.in' file was discovered.
   */
  public readonly stdin_file: string | null;
  /**
   * Path to a file with the expected standard output of the interpreter.
   * Present if the '.out' file was discovered.
   */
  public readonly expected_stdout_file: string | null;

  public constructor(init: TestCaseDefinitionFileInit) {
    this.name = init.name;
    this.test_source_path = init.test_source_path;
    this.stdin_file = init.stdin_file ?? null;
    this.expected_stdout_file = init.expected_stdout_file ?? null;
  }
}

export interface TestCaseDefinitionInit extends TestCaseDefinitionFileInit {
  test_type: TestCaseType;
  description?: string | null;
  category: string;
  points?: number;
  expected_parser_exit_codes?: number[] | null;
  expected_interpreter_exit_codes?: number[] | null;
}

export class TestCaseDefinition extends TestCaseDefinitionFile {
  /**
   * Represents a single discovered test case (that was successfully parsed).
   *
   * IPP: Do not modify this model directly, as it is also used in the output report.
   *      You may create your own internal models derived from this one.
   */

  /**
   * The type of the test case, which determines how it should be executed
   * and what exit codes are expected.
   */
  public readonly test_type: TestCaseType;
  /** An optional human-readable description of the test case. */
  public readonly description: string | null;
  /**
   * A string identifier of a category to which this test case belongs.
   * Used for grouping test cases in the final report and for filtering which test cases to execute.
   */
  public readonly category: string;
  /** The number of points awarded for passing this test case. */
  public readonly points: number;
  /**
   * A list of expected parser exit codes.
   * Must be present for parser-only test cases.
   * Must be null for interpreter-only test cases.
   * Must be null or [0] for combined test cases.
   */
  public readonly expected_parser_exit_codes: number[] | null;
  /**
   * A list of expected interpreter exit code.
   * Must be present for interpreter-only and combined test cases.
   * Must be null for parser-only test cases.
   */
  public readonly expected_interpreter_exit_codes: number[] | null;

  public constructor(init: TestCaseDefinitionInit) {
    super(init);
    this.test_type = init.test_type;
    this.description = init.description ?? null;
    this.category = init.category;
    this.points = init.points ?? 1;
    this.expected_parser_exit_codes = init.expected_parser_exit_codes ?? null;
    this.expected_interpreter_exit_codes = init.expected_interpreter_exit_codes ?? null;

    this.validateExitCodes();
  }

  private static hasNoExitCodes(exitCodes: number[] | null): boolean {
    return exitCodes === null || exitCodes.length === 0;
  }

  private validateParseOnlyExitCodes(): void {
    if (TestCaseDefinition.hasNoExitCodes(this.expected_parser_exit_codes)) {
      throw new Error("Expected parser exit codes must be provided for parse-only test cases.");
    }
    if (this.expected_interpreter_exit_codes !== null) {
      throw new Error(
        "Expected interpreter exit codes should not be provided for parse-only test cases."
      );
    }
  }

  private validateExecuteOnlyExitCodes(): void {
    if (TestCaseDefinition.hasNoExitCodes(this.expected_interpreter_exit_codes)) {
      throw new Error(
        "Expected interpreter exit codes must be provided for execute-only test cases."
      );
    }
    if (this.expected_parser_exit_codes !== null) {
      throw new Error(
        "Expected parser exit codes should not be provided for execute-only test cases."
      );
    }
  }

  private validateCombinedExitCodes(): void {
    if (
      this.expected_parser_exit_codes !== null &&
      (this.expected_parser_exit_codes.length !== 1 || this.expected_parser_exit_codes[0] !== 0)
    ) {
      throw new Error("In combined test cases, the parser exit code must be zero.");
    }
    if (TestCaseDefinition.hasNoExitCodes(this.expected_interpreter_exit_codes)) {
      throw new Error("Expected interpreter exit codes must be provided for combined test cases.");
    }
  }

  private validateExitCodes(): void {
    /**
     * Validates that the expected exit codes are provided correctly based on the test case type.
     */
    switch (this.test_type) {
      case TestCaseType.PARSE_ONLY:
        this.validateParseOnlyExitCodes();
        return;
      case TestCaseType.EXECUTE_ONLY:
        this.validateExecuteOnlyExitCodes();
        return;
      case TestCaseType.COMBINED:
        this.validateCombinedExitCodes();
        return;
    }
  }
}

// ---- Output ----

export enum UnexecutedReasonCode {
  /** The test case was filtered out based on the provided include/exclude criteria. */
  FILTERED_OUT = 0,
  /** The test case file could not be parsed as a valid SOLtest. */
  MALFORMED_TEST_CASE_FILE = 1,
  /** The type of the test case could not be (unambiguously) determined from the provided specification. */
  CANNOT_DETERMINE_TYPE = 2,
  /** It was not possible to run the external executable that was required for the test. */
  CANNOT_EXECUTE = 3,
  /** Unexpected error. */
  OTHER = 4,
}

export class UnexecutedReason {
  /**
   * Represents the reason why a test case was not executed, including an optional
   * human-readable message.
   *
   * IPP: Choose a suitable message, it won't be evaluated automatically.
   */

  public constructor(
    public readonly code: UnexecutedReasonCode,
    public readonly message: string | null = null
  ) {}
}

export enum TestResult {
  /** Represents the result of an executed test case. */
  PASSED = "passed",
  UNEXPECTED_PARSER_EXIT_CODE = "parse_fail",
  UNEXPECTED_INTERPRETER_EXIT_CODE = "int_fail",
  INTERPRETER_RESULT_DIFFERS = "diff_fail",
}

export class TestCaseReport {
  /** Represents the report for a single test case after processing. */

  public constructor(
    public readonly result: TestResult,
    public readonly parser_exit_code: number | null = null,
    public readonly interpreter_exit_code: number | null = null,
    public readonly parser_stdout: string | null = null,
    public readonly parser_stderr: string | null = null,
    public readonly interpreter_stdout: string | null = null,
    public readonly interpreter_stderr: string | null = null,
    public readonly diff_output: string | null = null
  ) {}
}

export class CategoryReport {
  /** Represents the report for a category of test cases. */

  public constructor(
    /** The sum of points for all executed test cases in this category. */
    public readonly total_points: number,
    /** The sum of points for all passed test cases in this category. */
    public readonly passed_points: number,
    /** A mapping from test case names to their individual reports. */
    public readonly test_results: Record<string, TestCaseReport>
  ) {}
}

export interface TestReportInit {
  discovered_test_cases?: TestCaseDefinition[];
  unexecuted?: Record<string, UnexecutedReason>;
  results?: Record<string, CategoryReport> | null;
}

export class TestReport {
  /** Represents the report generated after processing the test cases. */

  /** A list of all discovered test cases that were successfully parsed. */
  public readonly discovered_test_cases: TestCaseDefinition[];
  /** A mapping from a test case name to the reason why it was not executed. */
  public readonly unexecuted: Record<string, UnexecutedReason>;
  public readonly results: Record<string, CategoryReport> | null;

  public constructor(init: TestReportInit) {
    this.discovered_test_cases = init.discovered_test_cases ?? [];
    this.unexecuted = init.unexecuted ?? {};
    this.results = init.results ?? null;
  }

  public toJSON(): Record<string, unknown> {
    const result: Record<string, unknown> = {
      discovered_test_cases: this.discovered_test_cases,
      unexecuted: this.unexecuted,
    };

    // The 'results' field is only included in the report if at least one test case was executed.
    if (this.results !== null && Object.keys(this.results).length > 0) {
      result["results"] = this.results;
    }

    return result;
  }
}
