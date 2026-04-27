"""Allow `python -m h_mesh_gateway` to run the CLI entrypoint."""

from h_mesh_gateway.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
