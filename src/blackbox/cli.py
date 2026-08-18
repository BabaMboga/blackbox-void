import click

@click.group()
def main():
    """Blackbox - Hide it.Lock it. Dare them to find it."""
    pass

@main.command()
def status():
    """Check that blackbox is installed and reachable."""
    click.echo("Blackbox is alive.")

if __name__ == "__main__":
    main()