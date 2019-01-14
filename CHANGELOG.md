# Changelog
All notable, unreleased changes to this project will be documented in this file. For the released changes, please visit the [Releases](https://github.com/mirumee/saleor/releases) page.

## [Unreleased]
- Use USERNAME_FIELD instead of hard-code email field when resolving user - #3577 by @jxltom
- Support returning user's checkouts in GraphQL API - #3578 by @fowczarek
- Catch GraphqQL syntax errors and output it to errors field - #3576 by @jxltom
- Register celery task for updating exchange rates - #3599 by @jxltom
- Order by id by default for CartLine - #3593 by @jxltom
