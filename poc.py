#!/usr/bin/env python

import argparse
import datetime
import os
import re
import shutil
import subprocess
import requests
import sys
import tempfile
import toml

from subprocess import PIPE, STDOUT

parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest="cmd")

parser_add = subparsers.add_parser("add")
parser_add.add_argument("crate", help="target crate name")
parser_add.add_argument("version", help="target crate version")

parser_run = subparsers.add_parser("run")
parser_run.add_argument("id", help="poc ID (4 digits)")
parser_run.add_argument("--copy", action="store_true", help="saves the PoC directory to `poc-debug` if set")

parser_report = subparsers.add_parser("report")
parser_report.add_argument("id", help="poc ID (4 digits)")
parser_report.add_argument("--preview", action="store_true", help="prints the report before reporting")
parser_report.add_argument("--crate_repo", action="store_true", help="reports the issue to the crate's repository")
parser_report.add_argument("--rustsec", action="store_true", help="reports the issue to RustSec advisory")

args = parser.parse_args()

# Read the configuration file
if not os.path.exists("config.toml"):
    print("`config.toml` does not exist")
    sys.exit(1)

with open("config.toml") as config_file:
    config_text = config_file.read()
    config = toml.loads(config_text)

user_name = config["name"]
user_email = config["email"]
user_token = config["token"]
rustsec_fork_url = config["rustsec_fork_url"]

# Check the environment
os_version = subprocess.check_output(["lsb_release", "-sd"]).decode().strip()

# Prepare Git repository
if not os.path.exists("advisory-db"):
    os.system(f"git clone {rustsec_fork_url} advisory-db")

# Map PoC number to PoC name
# Note that the name doesn't contain `.rs` extension
poc_id_to_name = {}

# Record known PoC
poc_dir_pattern = re.compile(r"(\d{4})-.+")

for name_with_ext in os.listdir("poc"):
    if os.path.isfile(f"poc/{name_with_ext}"):
        name = os.path.splitext(name_with_ext)[0]
        match = poc_dir_pattern.match(name)
        poc_id = match.group(1)
        poc_id_to_name[poc_id] = name

# Override rustc to enable the build cache
os.environ["RUSTC_WRAPPER"] = "sccache"

# Set LD_LIBRARY_PATH
link_path = os.path.abspath("dependencies")
if "LD_LIBRARY_PATH" in os.environ:
    os.environ["LD_LIBRARY_PATH"] += ":" + link_path
else:
    os.environ["LD_LIBRARY_PATH"] = link_path

# Set RUSTFLAGS
if "RUSTFLAGS" in os.environ:
    os.environ["RUSTFLAGS"] += " -A warnings"
else:
    os.environ["RUSTFLAGS"] = "-A warnings"


def read_metadata(poc_id):
    poc_name = poc_id_to_name[poc_id]

    with open(f"poc/{poc_name}.rs") as poc_file:
        lines = poc_file.readlines()
        if lines[0] == "/*!\n" and lines[1] == "```crux-poc\n":
            idx = lines.index("```\n")
            toml_str = ''.join(lines[2:idx])
            return toml.loads(toml_str)

    return None


# This method appends metadata to the last section, which is expected to be [report]
def append_metadata(poc_id, dict):
    poc_name = poc_id_to_name[poc_id]

    with open(f"poc/{poc_name}.rs") as poc_file:
        lines = poc_file.readlines()
        if lines[0] == "/*!\n" and lines[1] == "```crux-poc\n":
            idx = lines.index("```\n")
        else:
            raise Exception("PoC metadata comment not found")

    dict_toml = toml.dumps(dict)

    with open(f"poc/{poc_name}.rs", "w") as poc_file:
        poc_file.write("".join(lines[:idx]))
        poc_file.write(dict_toml)
        poc_file.write("".join(lines[idx:]))


def read_code(poc_id):
    poc_name = poc_id_to_name[poc_id]

    with open(f"poc/{poc_name}.rs") as poc_file:
        lines = poc_file.readlines()
        if lines[0] == "/*!\n" and lines[1] == "```crux-poc\n":
            idx = lines.index("!*/\n")
            return "".join(lines[idx+1:]).strip()

    raise Exception("Failed to read PoC code")


def prepare_report(poc_id):
    metadata = read_metadata(poc_id)
    code = read_code(poc_id)

    target_crate = metadata["target"]["crate"]
    target_version = metadata["target"]["version"]

    title = metadata["report"]["title"]
    description = metadata["report"]["description"]
    code_snippets = metadata["report"]["code_snippets"]

    # Add `--quiet` flag
    if "cargo_flags" in metadata["test"]:
        metadata["test"]["cargo_flags"].append("--quiet")
    else:
        metadata["test"]["cargo_flags"] = ["--quiet"]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        prepare_cargo_dir(poc_id, tmpdir)

        # parse `rustc` version
        metadata["test"]["cargo_flags"] += ["--", "--version"]
        cmd = prepare_cargo_cmd(metadata, "rustc")
        rustc_version = subprocess.run(cmd, stdout=PIPE, cwd=tmpdir).stdout.decode().strip()
        metadata["test"]["cargo_flags"] = metadata["test"]["cargo_flags"][:-2]

        cmd = prepare_cargo_cmd(metadata, "run")
        exec_result = subprocess.run(cmd, stdout=PIPE, stderr=STDOUT, cwd=tmpdir)
        exec_output = exec_result.stdout.decode().strip()
        exit_code = exec_result.returncode

    report_content = "".join(
        map(lambda s: s + "\n\n", code_snippets)
    )
    report_content += "# Description\n\n" + description
    report_content += f"""

# Demonstration

Crate: {target_crate}
Version: {target_version}
OS: {os_version}
Rust: {rustc_version}

```rust
{code}
```

Output:
```
{exec_output}
```

Return Code: {exit_code}
"""

    return {
        "title": title,
        "code": code,
        "description": report_content,
    }


def prepare_cargo_dir(poc_id, cargo_dir):
    poc_name = poc_id_to_name[poc_id]
    metadata = read_metadata(poc_id)

    # Cargo.toml
    with open(f"{cargo_dir}/Cargo.toml", "w") as manifest_file:
        manifest_content = f"""[package]
name = "crux-poc-{poc_id}"
version = "0.1.0"
authors = ["{user_name} <{user_email}>"]
edition = "2018"
build = "build.rs"

# See more keys and their definitions at https://doc.rust-lang.org/cargo/reference/manifest.html

[dependencies]
{metadata["target"]["crate"]} = "={metadata["target"]["version"]}"
"""

        if "peer" in metadata["target"]:
            for crate in metadata["target"]["peer"]:
                manifest_content += f'''{crate["crate"]} = "={crate["version"]}"\n'''

        manifest_file.write(manifest_content)

    # build.rs
    with open(f"{cargo_dir}/build.rs", "w") as build_file:
        build_file.write(f"""fn main() {{
    println!("cargo:rustc-link-search={link_path}");
}}""")

    # main.rs
    os.mkdir(f"{cargo_dir}/src")
    shutil.copyfile(f"poc/{poc_name}.rs", f"{cargo_dir}/src/main.rs")


def prepare_cargo_cmd(metadata, subcommand):
    result = ["cargo"]

    if "cargo_toolchain" in metadata["test"]:
        result.append("+" + metadata["test"]["cargo_toolchain"])

    result.append(subcommand)

    if "cargo_flags" in metadata["test"]:
        result += metadata["test"]["cargo_flags"]

    return result


def cmd_add(args):
    for poc_id_num in range(10000):
        poc_id_str = str(poc_id_num).rjust(4, '0')
        if poc_id_str not in poc_id_to_name:
            break

    assert poc_id_str not in poc_id_to_name
    new_poc_file = f"poc/{poc_id_str}-{args.crate}.rs"
    with open(new_poc_file, "w") as f:
        f.write(f"""/*!
```crux-poc
[target]
crate = "{args.crate}"
version = "{args.version}"

[test]
analyzers = []

[report]
title = "issue title"
description = \"\"\"
issue description\"\"\"
code_snippets = []
patched = []
informational = "unsound"
```
!*/
#![forbid(unsafe_code)]

fn main() {{
    println!("Hello, World!")
}}
""")

    print(f"Created `{new_poc_file}` with version {args.version}")


def cmd_run(args):
    poc_id = args.id
    metadata = read_metadata(poc_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        prepare_cargo_dir(poc_id, tmpdir)

        # execute `cargo run` with proper flags
        cmd = prepare_cargo_cmd(metadata, "run")
        subprocess.run(cmd, cwd=tmpdir)

        if args.copy:
            shutil.rmtree("./poc-debug", ignore_errors=True)
            shutil.copytree(tmpdir, "./poc-debug")


def cmd_report_crate_repo(poc_id, report):
    poc_name = poc_id_to_name[poc_id]
    metadata = read_metadata(poc_id)

    print(f"Reporting {poc_name} to the crate repository")

    # Check if it was already reported
    if "issue_date" in metadata["report"]:
        issue_date = metadata["report"]["issue_date"]
        print(f"Already reported on {issue_date}")
        if "issue_url" in metadata["report"]:
            issue_url = metadata["report"]["issue_url"]
            print(f"Issue URL: {issue_url}")
        else:
            print("Issue URL does not exist")
        return

    target_crate = metadata["target"]["crate"]
    crate_metadata = requests.get(f"https://crates.io/api/v1/crates/{target_crate}").json()

    if "repository" in crate_metadata["crate"]:
        repository_url = crate_metadata["crate"]["repository"]
        print(f"Reporting to: {repository_url}")
    else:
        repository_url = None

    if repository_url is None:
        print("Repository URL not found in crates.io metadata")
    elif not repository_url.startswith("https://github.com/"):
        print("Automatic reporting is only supported for GitHub")
    else:
        # TODO: Use GitHub API to report the bug
        pass

    # Save metadata to the file
    """
    append_metadata(poc_id, {
        "issue_url": "TODO",
        "issue_date": datetime.date.today()
    })
    """


def cmd_report_rustsec(poc_id, report):
    pass


def cmd_report(args):
    if not args.crate_repo and not args.rustsec:
        args.crate_repo = True
        args.rustsec = True

    poc_id = args.id
    report = prepare_report(poc_id)
    if args.preview:
        print(f"Title:\n{report['title']}\n\nDescription:\n{report['description']}")

    if args.crate_repo:
        cmd_report_crate_repo(poc_id, report)

    if args.rustsec:
        cmd_report_rustsec(poc_id, report)


# TODO: cmd_generate


action_dict = {
    "add": cmd_add,
    "run": cmd_run,
    "report": cmd_report,
}

if args.cmd is None:
    parser.print_help()
    sys.exit(1)

action = action_dict[args.cmd]
action(args)
