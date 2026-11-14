"""Discuter avec l'assistant dans le terminal.

Usage :
    python -m novatech.assistant                         # conversation interactive
    python -m novatech.assistant "Livrez-vous en Suisse ?"   # une seule question
    python -m novatech.assistant --details               # affiche les appels d'outils
"""

import argparse
import json
import sys

import anthropic

from .agent import Assistant, Conversation


def show_reply(conversation: Conversation, question: str, details: bool) -> None:
    try:
        reply = conversation.send(question)
    except anthropic.AuthenticationError:
        sys.exit("Clé API invalide : vérifiez ANTHROPIC_API_KEY dans le fichier .env.")
    except anthropic.APIConnectionError:
        print("\n[Connexion à l'API Claude impossible : vérifiez votre accès Internet.]\n")
        return
    except anthropic.APIStatusError as exc:
        print(f"\n[Erreur de l'API Claude ({exc.status_code}) : {exc.message}]\n")
        return

    if details:
        for call in reply.tool_calls:
            tool_input = json.dumps(call.input, ensure_ascii=False)
            print(f"  ⚙ {call.name}({tool_input})" + ("  → erreur" if call.is_error else ""))
    print(f"\n{reply.text}\n")
    if details:
        u = reply.usage
        print(f"  [tokens en entrée : {u['input_tokens']} normaux, "
              f"{u['cache_creation_input_tokens']} écrits en cache, "
              f"{u['cache_read_input_tokens']} lus depuis le cache ; "
              f"{u['output_tokens']} en sortie]")
        if reply.alerts:
            print(f"  ⚠ garde-fous déclenchés : {', '.join(reply.alerts)}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="NovaTech Assist dans le terminal")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--details", action="store_true", help="affiche outils, tokens et contrôles")
    args = parser.parse_args()

    conversation = Assistant().new_conversation()
    if args.question:
        show_reply(conversation, args.question, args.details)
        return 0

    print("NovaTech Assist — tapez votre question (ou « quitter »).\n")
    while True:
        try:
            question = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quitter", "exit", "quit"}:
            break
        if question:
            show_reply(conversation, question, args.details)
    return 0


if __name__ == "__main__":
    sys.exit(main())
