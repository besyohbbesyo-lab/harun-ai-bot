#!/usr/bin/env python3
"""
Harun AI Lab - Fast Start Version with PC Control
"""

import sys

from colorama import Fore, Style, init

from pc_control_plugin import PCControl

init(autoreset=True)

print(f"""
{Fore.CYAN}==================================================
         HARUN AI RESEARCH LAB v1.0.0
         Fast Start Edition + PC Control
=================================================={Style.RESET_ALL}

Type 'help' for commands
""")


def print_help():
    help_text = f"""
{Fore.GREEN}Available Commands:{Style.RESET_ALL}

{Fore.YELLOW}Basic:{Style.RESET_ALL}
  help     - Show this help
  status   - System status
  test     - Test chat (mock)
  exit     - Exit program

{Fore.YELLOW}PC Control:{Style.RESET_ALL}
  mkdir <path>           - Create folder
  mkfile <path>          - Create file
  open <program>         - Open program (notepad, chrome, calculator)
  move <from> <to>       - Move file
  list <path>            - List files in folder
"""
    print(help_text)


def chat_mock(message):
    """Mock chat"""
    responses = {
        "merhaba": "Merhaba! Ben Harun AI. PC kontrolü artık aktif!",
        "nasilsin": "Harika! PC kontrol özellikleri eklendi. 'help' yaz.",
        "test": "Test basarili! PC kontrol sistemi calisiyor!",
    }

    message_lower = message.lower()
    for key, response in responses.items():
        if key in message_lower:
            return response

    return f"Mesajinizi aldim: '{message}'"


def show_status():
    print(f"\n{Fore.CYAN}System Status:{Style.RESET_ALL}")
    print("  Mode: Fast Start + PC Control")
    print("  Status: Running")
    print("  PC Control: Active")
    print("  Ready: Yes\n")


def main():
    pc = PCControl()

    while True:
        try:
            user_input = input(f"{Fore.GREEN}> {Style.RESET_ALL}").strip()

            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if command == "exit":
                print(f"{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
                break

            elif command == "help":
                print_help()

            elif command == "status":
                show_status()

            elif command == "test" or command == "chat":
                message = args if args else "test"
                response = chat_mock(message)
                print(f"{Fore.CYAN}AI: {Style.RESET_ALL}{response}")

            elif command == "mkdir":
                if args:
                    result = pc.create_folder(args)
                    print(f"{Fore.GREEN}{result}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: mkdir <path>{Style.RESET_ALL}")

            elif command == "mkfile":
                if args:
                    result = pc.create_file(args)
                    print(f"{Fore.GREEN}{result}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: mkfile <path>{Style.RESET_ALL}")

            elif command == "open":
                if args:
                    result = pc.open_program(args)
                    print(f"{Fore.GREEN}{result}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: open <program>{Style.RESET_ALL}")
                    print(
                        f"{Fore.YELLOW}Available: notepad, chrome, calculator, explorer{Style.RESET_ALL}"
                    )

            elif command == "move":
                if args:
                    parts = args.split(maxsplit=1)
                    if len(parts) == 2:
                        result = pc.move_file(parts[0], parts[1])
                        print(f"{Fore.GREEN}{result}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Usage: move <from> <to>{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: move <from> <to>{Style.RESET_ALL}")

            elif command == "list":
                if args:
                    result = pc.list_files(args)
                    if isinstance(result, list):
                        print(f"\n{Fore.CYAN}Files in {args}:{Style.RESET_ALL}")
                        for item in result:
                            print(f"  - {item}")
                        print()
                    else:
                        print(f"{Fore.RED}{result}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Usage: list <path>{Style.RESET_ALL}")

            else:
                print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
                print("Type 'help' for available commands")

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Use 'exit' to quit{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
