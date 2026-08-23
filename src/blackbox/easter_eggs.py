"""
blackbox.easter_eggs - trivia facts and fake ominous system messages, shown on each access attempt.

This module is pure flavor. Nothing here touches passwords, keys or encryption logic - it exists purely to make unlocking The Void a
little more entertaining than a blank password prompt. The "ominous" messages are deliberately campy, not actually threatening: the goal
is a wink at hacker-movie tropes, not intimidation.

Did you know: the word "trivia" comes from Latin "trivium," literally "the place where three roads meet" - a crossroads, historically where
casual gossip and small talk happened. So "trivia" has meant "unimportant roadside chatter" for about two thousand years running.
"""

from __future__ import annotations

import random

from rich.console import Console

# --- Real trivia ------
# A mix of genuine facts about cryptography, computing history and a few callbacks to things already mentioned elsewhere in this project's 
# own docstrings - consistent voice throughout.

TRIVIA_FACTS = [
    "Argon2 is named after the noble gas argon — inert, colorless, "
    "and famously hard to react with. Fitting, for something whose "
    "entire job is to resist being cracked open.",
 
    "GCM stands for \"Galois/Counter Mode\" — named after Évariste "
    "Galois, a mathematician who did some of his most important work "
    "the night before a fatal duel at age 20.",
 
    "The Unix dotfile convention is, famously, an accident. The "
    "original `ls` simply skipped any entry starting with \".\" "
    "because that's how \".\" and \"..\" were implemented — the "
    "convention stuck for fifty years.",
 
    "The concept of a mathematical \"void\" (the empty set) was "
    "formalized by Ernst Zermelo in 1908 — meaning the idea of "
    "\"nothing\" is, itself, younger than the light bulb.",
 
    "The word \"password\" has been used in its modern sense since "
    "at least 1798 — long before computers, back when it just meant "
    "a spoken word that proved you belonged somewhere.",
 
    "AES, the encryption standard behind this vault, was originally "
    "called Rijndael, after its two Belgian creators Vincent Rijmen "
    "and Joan Daemen. NIST renamed it for the 2001 standard because, "
    "reportedly, almost nobody could pronounce it correctly.",
 
    "The first known use of a substitution cipher dates to Julius "
    "Caesar, who reportedly shifted every letter by three to keep "
    "military messages readable only by his generals.",
 
    "A single failed Argon2id attempt on modern hardware costs "
    "roughly the same computational effort as this vault's entire "
    "encryption step — which is exactly the point. Slow by design.",
 
    "The term \"salt\" in cryptography dates to at least the 1970s "
    "Unix password systems — the metaphor being that salting "
    "(seasoning) each password individually keeps two identical "
    "dishes from tasting the same.",
 
    "There is no such thing as \"unhackable.\" There is only "
    "\"expensive enough to not be worth it.\" This vault aims for "
    "the second one.",

    "The word \"cryptography\" comes from the Greek words "
    "`kryptos` (hidden) and `graphein` (writing) — literally "
    "\"hidden writing.\" Humans have been trying to keep secrets "
    "from each other for thousands of years.",

    "SHA-256 produces a 256-bit hash, meaning there are 2^256 "
    "possible outputs. That's a number so large that writing it "
    "out in full would be considerably less fun than just trusting "
    "the mathematics.",

    "The first computer password system was developed at MIT's "
    "Compatible Time-Sharing System in the 1960s. The system was "
    "designed to give different users their own private files — "
    "and researchers eventually discovered that even passwords "
    "can become interesting when humans are involved.",

    "Claude Shannon, one of the founders of modern information "
    "theory, published his landmark paper on communication secrecy "
    "in 1949. His work helped establish the mathematical foundations "
    "behind many of the ideas modern cryptography relies upon.",

    "A nonce is short for \"number used once.\" In authenticated "
    "encryption modes such as GCM, accidentally reusing a nonce "
    "with the same key can have serious consequences — proving that "
    "sometimes cryptography really does mean exactly what it says.",

    "The word \"cipher\" comes from the Arabic word \"sifr,\" meaning "
    "\"zero\" or \"empty.\" Medieval Europeans adopted the word while "
    "learning the Hindu-Arabic numeral system — so one of cryptography's "
    "most important words is literally connected to nothing.",

    "The Enigma machine used by Nazi Germany had an enormous number "
    "of possible configurations, but its security ultimately depended "
    "on both mathematics and operational discipline. Even excellent "
    "cryptography can be undermined when humans reuse keys or make "
    "predictable mistakes.",

    "Public-key cryptography allows someone to publish a key openly "
    "while keeping another key secret. The surprising part is that "
    "the public key can be used to protect information without "
    "revealing the private key — rather like giving everyone a lock "
    "while keeping the only key to yourself.",

    "The hexadecimal system is especially popular among programmers "
    "because every hexadecimal digit represents exactly four bits. "
    "That means two hexadecimal characters neatly represent one byte — "
    "which is why cryptographic hashes often look like long strings "
    "of numbers and letters.",

    "Randomness is one of cryptography's quiet superpowers. A password "
    "can be excellent, but predictable salts, keys, or nonces can still "
    "weaken a system. Good cryptographic software therefore relies on "
    "randomness generated by the operating system rather than guessing "
    "what \"random\" should look like.",
]

# --- Fake ominous system messages ----
# Purely theatrical. None of these correspond to anything real happening under the hood - they're a wink at hacker-movie tropes, not a
# not a genuine threat or an attempt to actually intimidate anyone.

FAKE_SYSTEM_MESSAGES = [
    "Rerouting request through seventeen proxy servers... "
    "(there are zero proxy servers)",
 
    "Cross-referencing biometric signature database... "
    "(this vault does not have a camera)",
 
    "Alerting local authorities of unauthorized access attempt... "
    "(it is not)",
 
    "Engaging quantum decryption countermeasures... "
    "(quantum computers cannot help you here, or anywhere, yet)",
 
    "Pinging mainframe for authorization override... "
    "(there is no mainframe)",
 
    "Deploying countersurveillance protocols... "
    "(the only surveillance here is you, reading this)",
 
    "Initiating self-destruct sequence in 3... 2... "
    "(there is no self-destruct sequence)",
 
    "Notifying your IT department of this attempt... "
    "(you do not have an IT department)",
 
    "Compiling dossier on unauthorized user... "
    "(it contains one entry: \"tried a password\")",
 
    "Activating laser grid... "
    "(there is, upsettingly, no laser grid)",

    "Consulting the Oracle of Cryptographic Wisdom... "
    "(the Oracle is currently unavailable for comment)",

    "Checking satellite uplink for secondary authentication... "
    "(the satellite has better things to do)",

    "Deploying twelve highly trained security hamsters... "
    "(the hamsters have unionized)",

    "Scanning the vault for hostile lifeforms... "
    "(one suspicious lifeform detected: you)",

    "Establishing encrypted communication with the Pentagon... "
    "(the Pentagon was not consulted about this)",

    "Calculating probability of successful intrusion... "
    "(calculation terminated after discovering you know the password)",

    "Activating emergency anti-hacker lasers... "
    "(budget constraints have unfortunately cancelled the lasers)",

    "Contacting the ancient custodians of The Void... "
    "(they left no forwarding address)",

    "Running advanced facial recognition protocol... "
    "(Blackbox has neither a face nor the emotional capacity to care)",

    "Consulting 47 terabytes of classified intelligence... "
    "(the database contains mostly cat pictures and questionable PDFs)",
]

def get_random_trivia() -> str:
    """
    Return one randomly chosen trivia fact
    """

    return random.choice(TRIVIA_FACTS)

def get_random_system_message() -> str:
    """
    Return one randomly chosen fake ominous system message
    """

    return random.choice(FAKE_SYSTEM_MESSAGES)

def print_random_trivia(console: Console | None = None) -> None:
    """
    Print one randomly chosen trivia fact to the console.

    Args:
        console: an existing rich Console to print to. If omitted, a new one is created - callers that already have a shared Console
            (e.g. the CLI) should pass it in, so output stays on the same stream/styling context. 
    """

    console = console or Console()
    console.print(f"[dim italic]Did you know: {get_random_trivia()}[/dim italic]")

def print_random_system_message(console: Console | None = None) -> None:
    """
    Print one randomly chosen fake ominous system message to the console.

    Args:
        console: an existing rich Console to print to. If omitted, a new one is created.
    """

    console = console or Console()
    console.print(f"[bold red]>> {get_random_system_message()}[/bold red]")

def print_access_attempt_flavor(console: Console | None = None) -> None:
    """
    Print one random piece of flavor text - either a real trivia fact or a fake ominous system message, chosen with equal probability 
    - intended to be called on each vault access attempt(lock or unlock).

    Args:
        console: an existing rich Console to print to. If omitted, a new one is created.
    """
    console = console or Console()
    if random.random() < 0.5:
        print_random_trivia(console)
    else:
        print_random_system_message(console)