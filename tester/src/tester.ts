#!/usr/bin/env node
/**
 * An integration testing script for the SOL26 interpreter.
 *
 * IPP: You can implement the entire tool in this file if you wish, but it is recommended to split
 *      the code into multiple files and modules as you see fit.
 *
 *      Below, you have some code to get you started with the CLI argument parsing and logging setup,
 *      but you are **free to modify it** in whatever way you like.
 *
 * Author: Ondřej Ondryáš <iondryas@fit.vut.cz>
 * Author: Patrik Lošťák <xlostap00>
 *
 * AI usage notice: The author used OpenAI Codex to create the implementation of this
 *                  module based on its Python counterpart.
 */

import {
  existsSync,
  lstatSync,
  writeFileSync,
  createReadStream,
  rmSync,
  readFileSync,
} from "node:fs";
import { dirname, resolve, join, basename } from "node:path";
import { parseArgs } from "node:util";
import { readdir, readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { Buffer } from "node:buffer";
import * as os from "node:os";

import {
  TestReport,
  TestCaseDefinition,
  TestCaseType,
  UnexecutedReason,
  UnexecutedReasonCode,
  CategoryReport,
  TestResult,
  TestCaseReport,
} from "./models.js";

import { pino } from "pino";
//import { exitCode } from "node:process";
//import test from "node:test";

const logger = pino({
  transport: {
    target: "pino-pretty",
    options: {
      colorize: true,
      destination: 2,
    },
  },
});

interface CliArguments {
  tests_dir: string;
  recursive: boolean;
  output: string | null;
  dry_run: boolean;
  include: string[] | null;
  include_category: string[] | null;
  include_test: string[] | null;
  exclude: string[] | null;
  exclude_category: string[] | null;
  exclude_test: string[] | null;
  verbose: number;
  regex_filters: boolean;
}

function writeResult(resultReport: TestReport, outputFile: string | null): void {
  /**
   * Writes the final report to the specified output file or standard output if no file is provided.
   */
  const resultJson = JSON.stringify(resultReport, null, 2);
  if (outputFile !== null) {
    writeFileSync(outputFile, resultJson, "utf8");
    return;
  }

  console.log(resultJson);
}

const DOUBLE_LETTER_SHORT_OPTION_NORMALIZATION = new Map<string, string>([
  ["-ic", "--include-category"],
  ["-it", "--include-test"],
  ["-ec", "--exclude-category"],
  ["-et", "--exclude-test"],
]);

const HELP_TEXT = [
  "Usage:",
  "  tester [options] tests_dir",
  "",
  "Positional arguments:",
  "  tests_dir                 Path to a directory with the test cases in the SOLtest format.",
  "",
  "Options:",
  "  -h, --help                Show this help message and exit.",
  "  -r, --recursive           Recursively search for test cases in subdirectories of the provided directory.",
  "  -o, --output <path>       The output file to write the test results to. If not provided, results will be printed to standard output.",
  "  --dry-run                 Perform a dry run: discover the test cases but don't actually execute them.",
  "  -i, --include <value>     Include only test cases with the specified name or category. Can be used multiple times to specify multiple criteria.Can be combined with -ic and -it.",
  "  -ic, --include-category <value>",
  "                            Include only test cases with the specified category. Can be used multiple times to specify multiple accepted categories. Can be combined with -it and -i.",
  "  -it, --include-test <value>",
  "                            Include only test cases with the specified name. Can be used multiple times to specify multiple accepted names. Can be combined with -ic and -i.",
  "  -e, --exclude <value>     Exclude test cases with the specified name or category. Can be used multiple times to specify multiple criteria.Can be combined with -ic and -it.",
  "  -ec, --exclude-category <value>",
  "                            Exclude test cases with the specified category. Can be used multiple times to specify multiple accepted categories. Can be combined with -it and -i.",
  "  -et, --exclude-test <value>",
  "                            Exclude test cases with the specified name. Can be used multiple times to specify multiple accepted names. Can be combined with -ic and -i.",
  "  -g                        When used, the filters specified with -i[ct]/-e[ct] will be interpreted as regular expressions instead of literal strings.",
  "  -v, --verbose             Enable verbose logging output (using once = INFO level, using twice = DEBUG level).",
];

const PARSE_OPTIONS = {
  help: { type: "boolean", short: "h", default: false },
  recursive: { type: "boolean", short: "r", default: false },
  output: { type: "string", short: "o" },
  "dry-run": { type: "boolean", default: false },
  include: { type: "string", short: "i", multiple: true },
  "include-category": { type: "string", multiple: true },
  "include-test": { type: "string", multiple: true },
  exclude: { type: "string", short: "e", multiple: true },
  "exclude-category": { type: "string", multiple: true },
  "exclude-test": { type: "string", multiple: true },
  "regex-filters": { type: "boolean", short: "g", default: false },
  verbose: { type: "boolean", short: "v", multiple: true },
} as const;

function normalizeArgv(argv: string[]): string[] {
  return argv.map((arg) => DOUBLE_LETTER_SHORT_OPTION_NORMALIZATION.get(arg) ?? arg);
}

function printHelp(): void {
  console.log(HELP_TEXT.join("\n"));
}

function listOrNull(values: string[] | undefined): string[] | null {
  if (values === undefined || values.length === 0) {
    return null;
  }

  return values;
}

function parseCliArgumentsRaw(argv: string[]) {
  return parseArgs({
    args: normalizeArgv(argv),
    options: PARSE_OPTIONS,
    allowPositionals: true,
    strict: true,
  } as const);
}

function parseArguments(): CliArguments {
  /**
   * Parses the command-line arguments and performs basic validation a sanitization.
   */
  let parsed: ReturnType<typeof parseCliArgumentsRaw>;

  try {
    parsed = parseCliArgumentsRaw(process.argv.slice(2));
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    process.exit(2);
  }

  const parsedValues = parsed.values;

  if (parsedValues["help"]) {
    printHelp();
    process.exit(0);
  }

  if (parsed.positionals.length !== 1 || parsed.positionals[0] === undefined) {
    console.error("Exactly one positional argument (tests_dir) is required.");
    process.exit(2);
  }

  const args: CliArguments = {
    tests_dir: resolve(parsed.positionals[0]),
    recursive: parsedValues["recursive"],
    output: parsedValues["output"] ?? null,
    dry_run: parsedValues["dry-run"],
    include: listOrNull(parsedValues["include"]),
    include_category: listOrNull(parsedValues["include-category"]),
    include_test: listOrNull(parsedValues["include-test"]),
    exclude: listOrNull(parsedValues["exclude"]),
    exclude_category: listOrNull(parsedValues["exclude-category"]),
    exclude_test: listOrNull(parsedValues["exclude-test"]),
    verbose: parsedValues["verbose"]?.length ?? 0,
    regex_filters: parsedValues["regex-filters"],
  };

  // Check source directory
  if (!existsSync(args.tests_dir) || !lstatSync(args.tests_dir).isDirectory()) {
    console.error("The provided path is not a directory.");
    process.exit(1);
  }

  // Warn if the output file already exists
  if (args.output !== null) {
    const outputParent = dirname(args.output);
    if (!existsSync(outputParent)) {
      console.error("The parent directory of the output file does not exist.");
      process.exit(1);
    }

    if (existsSync(args.output)) {
      logger.warn("The output file will be overwritten: %s", args.output);
    }
  }

  return args;
}

async function findTests(dirPath: string, recursive: boolean): Promise<string[]> {
  /**s
   * Recursively finds all test case files in the specified directory.
   * @param dirPath The directory to search for test case files.
   * @param recursive Whether to search subdirectories recursively.
   * @returns A promise that resolves to an array of file paths for the discovered test cases.
   */
  const testFiles: string[] = [];

  try {
    // Read the contents of the dir
    const entries = await readdir(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = join(dirPath, entry.name);
      if (entry.isDirectory()) {
        if (recursive) {
          // Recursively search the subdirectory
          const subDirTests = await findTests(fullPath, recursive);
          testFiles.push(...subDirTests);
        }
      } else if (entry.isFile() && entry.name.endsWith(".test")) {
        // Found a test case file
        testFiles.push(fullPath);
      }
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error(`Couldn't read directory ${dirPath}: ${msg}`);
  }
  return testFiles;
}
// The struct to hold data from test file
interface TestData {
  desc: string | null;
  cat: string;
  ptsWeight: number;
  expParserExCodes: number[] | null;
  expIntExCodes: number[] | null;
  srcCodeLines: string[];
}
// Parse header data from test file
function parseHeaderData(line: string, data: TestData): void {
  if (line.startsWith("***")) {
    data.desc = line.substring(3).trim();
  } else if (line.startsWith("+++")) {
    data.cat = line.substring(3).trim();
  } else if (line.startsWith(">>>")) {
    data.ptsWeight = Number(line.substring(3).trim());
  } else if (line.startsWith("!C!")) {
    if (!data.expParserExCodes) {
      data.expParserExCodes = [];
    }
    data.expParserExCodes.push(Number(line.substring(3).trim()));
  } else if (line.startsWith("!I!")) {
    if (!data.expIntExCodes) {
      data.expIntExCodes = [];
    }
    data.expIntExCodes.push(Number(line.substring(3).trim()));
  }
}
// helper func to parse the test file hdr and src code
function getHeaderAndCode(lines: string[]): TestData {
  let isHeader = true;
  const data: TestData = {
    desc: null,
    cat: "",
    ptsWeight: 1,
    expParserExCodes: null,
    expIntExCodes: null,
    srcCodeLines: [],
  };

  for (const line of lines) {
    if (isHeader) {
      if (line.trim() === "") {
        isHeader = false;
        continue;
      }
      parseHeaderData(line, data);
    } else {
      data.srcCodeLines.push(line);
    }
  }

  return data;
}
// helper func to determine the test type
function chooseTestType(
  parserCodes: number[] | null,
  intCodes: number[] | null,
  testName: string
): TestCaseType {
  if (parserCodes !== null && intCodes === null) {
    return TestCaseType.PARSE_ONLY;
  } else if (parserCodes === null && intCodes !== null) {
    return TestCaseType.EXECUTE_ONLY;
  } else if (parserCodes !== null && intCodes !== null) {
    return TestCaseType.COMBINED;
  } else {
    throw new Error(`Test type of ${testName} cannot be determined.`);
  }
}

async function parseTests(testFilePath: string): Promise<TestCaseDefinition | null> {
  /**
   * Parses a test case definition from the specified file.
   * @param testFilePath The path to the test case file.
   * @returns A promise that resolves to a TestCaseDefinition object and null on error
   */
  try {
    const fileData = await readFile(testFilePath, "utf8");
    const lines = fileData.split(/\r?\n/);

    // Remove the .test from name
    const name = testFilePath.substring(
      testFilePath.lastIndexOf("/") + 1,
      testFilePath.lastIndexOf(".")
    );

    // Check for .in and .out files
    const path = testFilePath.substring(0, testFilePath.lastIndexOf("."));
    const stdinFile = existsSync(`${path}.in`) ? `${path}.in` : null;
    const expOutFile = existsSync(`${path}.out`) ? `${path}.out` : null;

    const headerAndCode = getHeaderAndCode(lines);

    if (!headerAndCode.cat) {
      logger.error(`Test case ${name} does not have a category specified.`);
      return null;
    }

    const testType = chooseTestType(
      headerAndCode.expParserExCodes,
      headerAndCode.expIntExCodes,
      name
    );

    return new TestCaseDefinition({
      test_type: testType,
      description: headerAndCode.desc,
      category: headerAndCode.cat,
      points: headerAndCode.ptsWeight,
      expected_parser_exit_codes: headerAndCode.expParserExCodes,
      expected_interpreter_exit_codes: headerAndCode.expIntExCodes,
      name,
      test_source_path: testFilePath,
      stdin_file: stdinFile,
      expected_stdout_file: expOutFile,
    });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to parse test case file ${testFilePath}: ${msg}`);
    return null;
  }
}
// helper func to match test case against defined filters
function matchTestCase(value: string, filters: string[] | null, regex: boolean): boolean {
  if (filters === null || filters.length === 0) {
    return false;
  }

  for (const filter of filters) {
    if (regex) {
      try {
        const regexObj = new RegExp(filter);
        if (regexObj.test(value)) {
          return true;
        }
      } catch (error) {
        // If the regex is invalid, skip it
        const msg = error instanceof Error ? error.message : String(error);
        logger.debug(`Invalid regex expression: ${filter}, error: ${msg}`);
      }
    } else {
      // Literal string match
      if (value === filter.trim()) {
        return true;
      }
    }
  }

  return false;
}

// helper func to load and parse all test cases from the provided files
async function loadAllTests(
  testFiles: string[]
): Promise<{ tests: TestCaseDefinition[]; unexecuted: Record<string, UnexecutedReason> }> {
  const tests: TestCaseDefinition[] = [];
  const unexecuted: Record<string, UnexecutedReason> = {};

  for (const path of testFiles) {
    const testCase = await parseTests(path);
    if (testCase !== null) {
      tests.push(testCase);
    } else {
      const name = path.substring(path.lastIndexOf("/") + 1, path.lastIndexOf("."));
      unexecuted[name] = new UnexecutedReason(
        UnexecutedReasonCode.MALFORMED_TEST_CASE_FILE,
        "Failed to parse the test case file."
      );
    }
  }
  return { tests, unexecuted };
}

// helper func to find out if test case should be inlcuded based on the provided filters
function isIncluded(
  test: TestCaseDefinition,
  args: CliArguments,
  hasIncludeFilters: boolean
): boolean {
  if (!hasIncludeFilters) {
    return true;
  }

  const matchName =
    matchTestCase(test.name, args.include_test, args.regex_filters) ||
    matchTestCase(test.name, args.include, args.regex_filters);
  const matchCat =
    matchTestCase(test.category, args.include_category, args.regex_filters) ||
    matchTestCase(test.category, args.include, args.regex_filters);

  return matchName || matchCat;
}
// helper func to find out if test case should be excluded based on the provided filters
function isExcluded(test: TestCaseDefinition, args: CliArguments): boolean {
  return (
    matchTestCase(test.name, args.exclude_test, args.regex_filters) ||
    matchTestCase(test.name, args.exclude, args.regex_filters) ||
    matchTestCase(test.category, args.exclude_category, args.regex_filters) ||
    matchTestCase(test.category, args.exclude, args.regex_filters)
  );
}

function filterTests(
  tests: TestCaseDefinition[],
  args: CliArguments,
  unexecuted: Record<string, UnexecutedReason>
): TestCaseDefinition[] {
  const filteredTests: TestCaseDefinition[] = [];
  const hasIncludeFilters =
    (args.include !== null && args.include.length > 0) ||
    (args.include_category !== null && args.include_category.length > 0) ||
    (args.include_test !== null && args.include_test.length > 0);

  for (const test of tests) {
    if (isIncluded(test, args, hasIncludeFilters) && !isExcluded(test, args)) {
      filteredTests.push(test);
    } else {
      unexecuted[test.name] = new UnexecutedReason(
        UnexecutedReasonCode.FILTERED_OUT,
        "The test case was filtered out by provided filters."
      );
    }
  }

  return filteredTests;
}

interface ProccessResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

async function execCommand(
  command: string,
  args: string[],
  stdinFile: string | null = null,
  inputData: string | null = null,
  cwd?: string // working directory for the process
): Promise<ProccessResult> {
  /**
   * Executes a command with the specified arguments and optional standard input.
   * @param command The command to execute (e.g., the path to the interpreter).
   * @param args The arguments to pass to the command.
   * @param stdinFile An optional file path to use as stdout for the command.
   * @param inputData An optional string to use as stdin for the command. Ignored if stdinFile is provided.
   * @param cwd The working directory to execute the command in.
   * @returns A promise that resolves to an object containing the exit code, stdout, stderr
   */
  return new Promise((resolve) => {
    const proc = spawn(command, args, { cwd: cwd });

    let stdout = "";
    let stderr = "";
    proc.on("error", (err) => {
      resolve({ exitCode: -1, stdout: "", stderr: `Failed to run ${command}: ${err.message}` });
    });
    // Capture standard output
    proc.stdout.on("data", (data: Buffer) => {
      stdout += data.toString("utf-8");
    });
    // Capture standard error
    proc.stderr.on("data", (data: Buffer) => {
      stderr += data.toString("utf-8");
    });

    // Handle process exit
    proc.on("close", (code) => {
      resolve({ exitCode: code !== null ? code : -1, stdout, stderr });
    });

    // If a stdin file is provided, pipe it to the process
    if (stdinFile !== null) {
      const readStream = createReadStream(stdinFile);
      readStream.pipe(proc.stdin);
    } else if (inputData !== null) {
      // If input data is provided, write it to the process's stdin
      proc.stdin.write(inputData);
      proc.stdin.end();
    } else {
      // No input, just close stdin
      proc.stdin.end();
    }
  });
}

const toNull = (val: string) => (val === "" ? null : val);

function getSrcCode(testPath: string): string {
  const data = readFileSync(testPath, "utf8");
  const lines = data.split(/\r?\n/);
  let isHeader = true;
  const codeLines: string[] = [];

  for (const line of lines) {
    if (isHeader) {
      if (line.trim() === "") {
        isHeader = false;
      }
    } else {
      codeLines.push(line);
    }
  }
  const tempPath = join(os.tmpdir(), `${basename(testPath)}.temp.src`);
  writeFileSync(tempPath, codeLines.join("\n"), "utf8");
  return tempPath;
}

async function runParser(test: TestCaseDefinition, parserPath: string, codeSrcPath: string) {
  const srcCode = readFileSync(codeSrcPath, "utf8").trim();
  // Check if it is xml already
  const isXml = srcCode.startsWith("<?xml") || srcCode.startsWith("<program");
  let exCode = 0;
  let stdout = "";
  let stderr = "";

  if (isXml) {
    // dont run parser, just copy content
    stdout = srcCode;
  } else {
    const parserRes = await execCommand("python3", [parserPath, codeSrcPath], test.stdin_file);
    exCode = parserRes.exitCode;
    stdout = parserRes.stdout;
    stderr = parserRes.stderr;
  }
  // Check if parser ended good
  let isOk = true;
  if (test.test_type === TestCaseType.PARSE_ONLY || test.test_type === TestCaseType.COMBINED) {
    isOk = test.expected_parser_exit_codes?.includes(exCode) ?? false;
  } else {
    // Exec only so expect 0 idk :)
    isOk = exCode === 0;
  }
  // Save xml to temp file
  let xmlPath = codeSrcPath;
  if (
    isOk &&
    (test.test_type === TestCaseType.EXECUTE_ONLY || test.test_type === TestCaseType.COMBINED)
  ) {
    // Write the parser output to a temp xml file for the interpreter to consume
    xmlPath = join(os.tmpdir(), `${basename(test.test_source_path)}.temp.xml`);
    writeFileSync(xmlPath, stdout, "utf8");
  }

  return {
    code: exCode,
    stdout: stdout,
    stderr: stderr,
    passed: isOk,
    xmlPath,
  };
}

async function runInterpreter(test: TestCaseDefinition, intPath: string, xmlPath: string) {
  if (test.test_type !== TestCaseType.EXECUTE_ONLY && test.test_type !== TestCaseType.COMBINED) {
    return { code: null, stdout: "", stderr: "", passed: true };
  }

  const intRes = await execCommand(
    "python3",
    ["src/solint.py", "-s", resolve(xmlPath)],
    test.stdin_file,
    null,
    intPath
  );
  const isOk = test.expected_interpreter_exit_codes?.includes(intRes.exitCode) ?? false;
  return { code: intRes.exitCode, stdout: intRes.stdout, stderr: intRes.stderr, passed: isOk };
}

async function compareOutput(test: TestCaseDefinition, intStdout: string) {
  if (test.expected_stdout_file === null) {
    return { stdout: "", passed: true };
  }

  const outTemp = join(os.tmpdir(), `${basename(test.test_source_path)}.temp.out`);
  writeFileSync(outTemp, intStdout, "utf8");

  const diffRes = await execCommand("diff", [test.expected_stdout_file, outTemp]);
  if (existsSync(outTemp)) {
    rmSync(outTemp);
  }

  return { stdout: diffRes.stdout, passed: diffRes.exitCode === 0 };
}

async function execOneTest(
  test: TestCaseDefinition,
  parserPath: string,
  intPath: string
): Promise<TestCaseReport> {
  /**
   * Executes a single test case and returns the result.
   * @param test The test case definition to execute.
   * @param parserPath The path to the parser executable.
   * @param intPath The path to the interpreter executable.
   * @returns A promise that resolves to a TestCaseReport object containing the results of the test execution.
   */

  let finalResult: TestResult = TestResult.PASSED;
  const codeSrcPath = getSrcCode(test.test_source_path);

  const parserRes = await runParser(test, parserPath, codeSrcPath);
  if (!parserRes.passed) {
    finalResult = TestResult.UNEXPECTED_PARSER_EXIT_CODE;
  }

  let intData: { code: number | null; stdout: string; stderr: string; passed: boolean } = {
    code: null,
    stdout: "",
    stderr: "",
    passed: true,
  };

  if (finalResult === TestResult.PASSED) {
    intData = await runInterpreter(test, intPath, parserRes.xmlPath);
    if (!intData.passed) {
      finalResult = TestResult.UNEXPECTED_INTERPRETER_EXIT_CODE;
    }
  }

  let diffOutput = "";
  if (finalResult === TestResult.PASSED) {
    const diffRes = await compareOutput(test, intData.stdout);
    diffOutput = diffRes.stdout;
    if (!diffRes.passed) {
      finalResult = TestResult.INTERPRETER_RESULT_DIFFERS;
    }
  }
  // clean up temp source code file
  if (existsSync(codeSrcPath)) {
    rmSync(codeSrcPath);
  }
  // clean up xml temp file
  if (parserRes.xmlPath.endsWith(".temp.xml") && existsSync(parserRes.xmlPath)) {
    rmSync(parserRes.xmlPath);
  }

  return new TestCaseReport(
    finalResult,
    parserRes.code,
    intData.code,
    toNull(parserRes.stdout),
    toNull(parserRes.stderr),
    toNull(intData.stdout),
    toNull(intData.stderr),
    toNull(diffOutput)
  );
}

async function executeAllTests(
  filteredTests: TestCaseDefinition[]
): Promise<Record<string, CategoryReport>> {
  const PARSER_PATH = resolve("int/sol2xml/sol_to_xml.py");
  const INT_PATH = resolve("int");
  const catReports: Record<string, CategoryReport> = {};

  for (const test of filteredTests) {
    logger.info(`Testing: ${test.name} [${test.category}]`);
    const testReport = await execOneTest(test, PARSER_PATH, INT_PATH);
    const isPassed = testReport.result === TestResult.PASSED;
    // Update category report
    const existingCatReport = catReports[test.category];
    const currPts = existingCatReport ? existingCatReport.total_points : 0;
    const currPassed = existingCatReport ? existingCatReport.passed_points : 0;
    const currResults = existingCatReport ? existingCatReport.test_results : {};

    currResults[test.name] = testReport;

    catReports[test.category] = new CategoryReport(
      currPts + test.points,
      currPassed + (isPassed ? test.points : 0),
      currResults
    );
  }

  return catReports;
}

async function main(): Promise<void> {
  /**
   * The main entry point for the SOL26 integration testing script.
   * It parses command-line arguments and executes the testing process.
   */

  // Set up logging
  // IPP: You do not have to use logging - but it is the recommended practice.
  //      See https://getpino.io/#/docs/api for more information.
  logger.level = "warn";

  // Parse the CLI arguments
  const args = parseArguments();

  // Enable debug or info logging if the verbose flag was set twice or once
  if (args.verbose >= 2) {
    logger.level = "debug";
  } else if (args.verbose === 1) {
    logger.level = "info";
  }

  logger.info(
    `Searching for tests in directory ${args.tests_dir}, recursive=${String(args.recursive)}`
  );
  const testFiles = await findTests(args.tests_dir, args.recursive);
  logger.info(`Found ${String(testFiles.length)} test case files.`);

  if (testFiles.length === 0) {
    logger.warn("No test cases found. Exiting...");
    const emptyReport = new TestReport({ discovered_test_cases: [], unexecuted: {}, results: {} });
    writeResult(emptyReport, args.output);
    return;
  }

  const { tests: testCases, unexecuted } = await loadAllTests(testFiles);
  logger.info(`Successfully parsed ${String(testCases.length)} test cases.`);

  const filteredTests = filterTests(testCases, args, unexecuted);
  logger.info(`After filtering, ${String(filteredTests.length)} test cases remain.`);

  // dry-run --> skip and write the report
  if (args.dry_run) {
    logger.info("Dry run enabled, skipping test execution.");
    const report = new TestReport({
      discovered_test_cases: testCases,
      unexecuted: unexecuted,
      results: null,
    });
    writeResult(report, args.output);
    return;
  }

  logger.info("Executing the test cases...");
  const catReports = await executeAllTests(filteredTests);

  logger.info("Testing completed. Writing the report...");
  const finalReport = new TestReport({
    discovered_test_cases: testCases,
    unexecuted: unexecuted,
    results: catReports,
  });
  writeResult(finalReport, args.output);
}

await main();
