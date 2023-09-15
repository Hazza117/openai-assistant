import json
import os
import subprocess
import time
from pathlib import Path

import click
import colorama
import openai

WORKING_DIR = Path(__file__).parent.resolve() / "working_dir"
FUNCTIONS = [
    {
        "name": "execute_python_file",
        "description": "Execute a python file with the given arguments",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename of the python script to execute",
                },
                "arguments": {
                    "type": "string",
                    "description": "The arguments to execute the file with",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "write_file",
        "description": "Write data to a file",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename to write to",
                },
                "data": {"type": "string", "description": "Data to write to the file"},
            },
            "required": ["filename", "data"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename of the file to read",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "list_files",
        "description": "List the files in the directory",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_python_file(filename: str, arguments: str | None = None) -> str:
    path = WORKING_DIR / filename
    os.chmod(str(path), 0o755)
    command = [f"python3", str(path)]
    if arguments:
        command += [arguments]
    system_log("EXECUTE", *[str(c) for c in command])

    try:
        out = subprocess.check_output(command, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        out = e.output.decode()
    system_log("RESULTS", out)

    return out


def write_file(filename: str, data: str) -> str:
    system_log("WRITE", filename)
    if not WORKING_DIR.exists():
        WORKING_DIR.mkdir()

    with open(WORKING_DIR / filename, "w") as f:
        f.write(data)

    return "File has been written"


def read_file(filename: str) -> str:
    system_log("READ", filename)
    try:
        with open(WORKING_DIR / filename, "r") as f:
            return f.read()
    except Exception as e:
        return str(e)


def list_files() -> str:
    results = ", ".join([str(f.name) for f in list(WORKING_DIR.iterdir())])
    system_log("LIST_FILES", results)
    return results


def get_gpt_response(
    messages: list[dict[str, str]], model: str
) -> openai.ChatCompletion:
    while True:
        try:
            return openai.ChatCompletion.create(
                model=model,
                messages=messages,
                functions=FUNCTIONS,
                function_call="auto",
            )
        except openai.error.RateLimitError:
            system_log("Rate limited!")
            time.sleep(60)
            continue


def system_log(*args):
    output = " ".join(args)
    print(f"{colorama.Fore.BLUE}{output}{colorama.Style.RESET_ALL}")


def get_user_input() -> str:
    print(f"{colorama.Fore.GREEN}User: {colorama.Style.RESET_ALL}", end="")
    return input()


@click.command()
@click.option("--model", default="gpt-4", help="The gpt model to use.")
@click.option(
    "--api-key",
    envvar="OPENAI_API_KEY",
    help="The OpenAI API key",
)
def assistant(model: str, api_key: str):
    if not api_key:
        raise ValueError(
            "OpenAI API needs to be passed as --api-key or set as "
            "OPENAI_API_KEY environment variable"
        )

    openai.api_key = api_key
    user_input = get_user_input()
    messages = [{"role": "user", "content": user_input}]
    response = get_gpt_response(messages, model)

    while True:
        response_message = response["choices"][0]["message"]
        messages.append(response_message)

        if content := response_message.get("content"):
            print(f"{colorama.Fore.RED}ASSISTANT: {colorama.Style.RESET_ALL}", content)
            print()

        # Call a function if the agent has chosen one, otherwise return the prompt to the user
        if response_message.get("function_call"):
            available_functions = {
                "execute_python_file": execute_python_file,
                "write_file": write_file,
                "read_file": read_file,
                "list_files": list_files,
            }
            function_name = response_message["function_call"]["name"]
            function_to_call = available_functions[function_name]
            function_args = json.loads(response_message["function_call"]["arguments"])
            function_response = function_to_call(**function_args)  # type: ignore[operator]
            messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": function_response,
                }
            )
        else:
            user_input = get_user_input()
            messages.append({"role": "user", "content": user_input})

        response = get_gpt_response(messages, model)
