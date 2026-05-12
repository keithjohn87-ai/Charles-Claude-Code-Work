"""Tiny target for Aider+MLX smoke test."""


def greet(name, greeting='Hello'):
    return f"{greeting}, {name}"


if __name__ == "__main__":
    print(greet("world"))
    print(greet('world', greeting='Howdy'))
