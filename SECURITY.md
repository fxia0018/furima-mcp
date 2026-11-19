# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub: **Security → Report a vulnerability** on this repository. Don't open a public issue for them.

Include what you found, how to reproduce it, and what an attacker could do with it. You should get a first reply within a week.

## Scope

furima-mcp runs locally as a subprocess of an MCP client. It makes outbound HTTPS requests to the four supported marketplaces only and stores nothing on disk. Things worth reporting include:

- a tool argument that makes the server request a host other than the supported marketplaces
- a tool argument that reads or writes local files, or runs code
- a way for page content returned by a site to break out of the JSON result

Listing text (titles, descriptions) is third-party content and is returned as data. MCP clients should treat it as untrusted, like any web page.

## Supported versions

Only the latest release gets fixes.
