#!/usr/bin/env node
/**
 * Installs the billing-engine agent skill into a project.
 *
 *   npx billing-engine-skill                # -> ./.claude/skills/billing-engine/SKILL.md
 *   npx billing-engine-skill --dest .agents/skills
 *   npx billing-engine-skill --dest .opencode/skill
 *   npx billing-engine-skill --print        # print SKILL.md to stdout
 *   npx billing-engine-skill --force        # overwrite an existing file
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_NAME = "billing-engine";
const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(HERE, "..", "SKILL.md");

function printHelp() {
  process.stdout.write(
    [
      "billing-engine-skill — install the billing-engine agent skill",
      "",
      "Usage:",
      "  npx billing-engine-skill [options]",
      "",
      "Options:",
      "  --dest <dir>   Skills root directory (default: .claude/skills)",
      "  --print        Print SKILL.md to stdout instead of writing a file",
      "  --force        Overwrite an existing SKILL.md",
      "  --help, -h     Show this help",
      "",
      "The skill is written to <dest>/billing-engine/SKILL.md.",
      "",
    ].join("\n"),
  );
}

function parseArgs(argv) {
  const options = { dest: ".claude/skills", print: false, force: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--print") {
      options.print = true;
    } else if (arg === "--force") {
      options.force = true;
    } else if (arg === "--dest") {
      const value = argv[i + 1];
      if (!value || value.startsWith("--")) {
        throw new Error("--dest requires a directory argument");
      }
      options.dest = value;
      i += 1;
    } else if (arg.startsWith("--dest=")) {
      options.dest = arg.slice("--dest=".length);
    } else {
      throw new Error(`unknown option: ${arg}`);
    }
  }
  return options;
}

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`${error.message}\n\n`);
    printHelp();
    process.exitCode = 2;
    return;
  }

  if (options.help) {
    printHelp();
    return;
  }

  if (!existsSync(SOURCE)) {
    process.stderr.write(`SKILL.md not found at ${SOURCE}\n`);
    process.exitCode = 1;
    return;
  }

  if (options.print) {
    process.stdout.write(readFileSync(SOURCE, "utf8"));
    if (!readFileSync(SOURCE, "utf8").endsWith("\n")) {
      process.stdout.write("\n");
    }
    return;
  }

  const targetDir = resolve(process.cwd(), options.dest, SKILL_NAME);
  const target = join(targetDir, "SKILL.md");

  if (existsSync(target) && !options.force) {
    process.stderr.write(
      `refusing to overwrite ${target}\n` +
        "pass --force to replace it, or choose another --dest\n",
    );
    process.exitCode = 1;
    return;
  }

  mkdirSync(targetDir, { recursive: true });
  copyFileSync(SOURCE, target);

  process.stdout.write(
    [
      `Installed the billing-engine skill:`,
      `  ${target}`,
      "",
      "Your coding agent will discover it automatically. For opencode use",
      "  npx billing-engine-skill --dest .opencode/skill",
      "",
    ].join("\n"),
  );
}

main();
