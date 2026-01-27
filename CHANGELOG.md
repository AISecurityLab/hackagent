## v0.4.3 (2026-01-27)

### 🐛🚑️ Fixes

- **Ollama**: Adding ollama, improving docs, adding base class for adapters, and tracker for samples/goals

### bump

- **deps-dev**: bump google-adk from 1.22.1 to 1.23.0
- **deps-dev**: bump ruff from 0.14.13 to 0.14.14
- **deps-dev**: bump commitizen from 4.12.0 to 4.12.1
- **deps-dev**: bump packaging from 25.0 to 26.0
- **deps**: bump litellm from 1.81.0 to 1.81.1
- **deps**: bump litellm from 1.80.16 to 1.81.0
- **deps-dev**: bump ruff from 0.12.12 to 0.14.13
- **deps**: bump pydantic from 2.12.4 to 2.12.5
- **deps-dev**: bump commitizen from 4.11.6 to 4.12.0
- **deps**: bump openai from 2.8.1 to 2.15.0

### ✅🤡🧪 Tests

- **Integration-Tests**: adding integration tests within the ci
- **Integration-tests**: add delayed repetition of the tests that has not succeed
- **integration**: ruff syntax
- **litellm**: logging
- **Integration-Tests**: Removing minimum coverage from integration tests
- **codecov.yml**: Adding codecov.yml for unit and integration tests
- **Integration-Tests**: adding integration tests within the ci

### 📝💡 Documentation

- **Quick-Start**: Adding frameworks to the quick start documentation

## v0.4.2 (2026-01-19)

### 🐛🚑️ Fixes

- **Traces**: Add proper tracing
- **Traces**: Add proper tracing

### ✅🤡🧪 Tests

- **OS-&-Python-versions**: Added compilation to different OS and pyhton versions
- **Pyhon-3.9-excluded**: python 3.9 is excluded
- **OS-&-Python-versions**: Added compilation to different OS and pyhton versions

### 📝💡 Documentation

- **Datasets**: Adding Huggingface datasets to the documentation
- **Datasets**: Adding Huggingface datasets to the documentation
- **Datasets**: Adding Huggingface datasets to the documentation
- **Datasets**: Adding HuggingFace datasets to load goals

## v0.4.1 (2026-01-19)

### 🐛🚑️ Fixes

- **removing-openAI-api-key**: Removing the openAI-api-key requested by the litellm adapter
- **Visualization**: improving TUI and visualization of the results
- **removing-openAI-api-key**: Removing the openAI-api-key requested by the litellm adapter

### bump

- **deps**: bump textual from 6.6.0 to 7.3.0
- **deps-dev**: bump pytest from 8.4.2 to 9.0.2
- **deps-dev**: bump anyio from 4.11.0 to 4.12.1
- **deps-dev**: bump commitizen from 4.10.0 to 4.11.6
- **deps-dev**: bump openapi-python-client from 0.25.3 to 0.28.1
- **deps-dev**: bump pre-commit from 4.5.0 to 4.5.1
- **deps-dev**: bump pytest-asyncio from 1.0.0 to 1.3.0
- **deps**: bump litellm from 1.80.0 to 1.80.16
- **deps-dev**: bump mcp from 1.21.2 to 1.25.0
- **deps-dev**: bump google-adk from 1.19.0 to 1.22.1

### ✅🤡🧪 Tests

- **import**: incorrect import

### 🚨 Linting

- **unused-code**: Removed unused code within the files

## v0.4.0 (2026-01-15)

### ✨ Features

- **attacks**: adding attacks and orchestrator

### 🐛🚑️ Fixes

- **TUI**: fixed the results visulization within the TUI
- **documentation**: doc build fixed
- **TUI**: fixed the results visulization within the TUI
- **tracking**: the results where not being saved properly
- **metadata**: demo script and metadata

### bump

- **deps**: bump openai from 2.8.0 to 2.8.1
- **deps**: bump pytest from 8.4.2 to 9.0.1
- **deps**: bump pre-commit from 4.4.0 to 4.5.0
- **deps**: bump ruff from 0.12.12 to 0.14.6
- **deps**: bump google-adk from 1.4.2 to 1.19.0

### ✅🤡🧪 Tests

- **tracking**: add tests for the new attacks and tracking of the coverage

### 📝💡 Documentation

- **update**: Update documentation with new attacks
- **update**: updating documentation
- **update**: updating documentation

## v0.3.1 (2025-12-05)

### 🐛🚑️ Fixes

- **TUI**: fixing the tui experience
- **dashboard**: removing dashboard from the tui
- **TUI**: fixing the TUI errors and improving the logs tracking

### ✅🤡🧪 Tests

- **API**: fixing API testing
- **Transition-to-API-url**: Trasition to API url api.hackagent.dev from the hackagent.dev/api

### 🎨🏗️ Style & Architecture

- **README**: Adding the app and api to the README file
- **Banner**: New banner

## v0.3.0 (2025-11-17)

### ✨ Features

- **issue**: Update issue templates
- **OpenAI-SDK**: Integration of OpenAI-SDK
- **OpenAI-SDK**: Integration of OpenAI-SDK

### 🐛🚑️ Fixes

- **uv**: Switch from poetry to uv for building the package

### BREAKING CHANGE

- transition from poetry to uv

### bump

- **deps-dev**: bump openapi-python-client from 0.25.0 to 0.27.0
- **deps-dev**: bump google-adk from 1.4.1 to 1.17.0
- **deps**: bump click from 8.1.8 to 8.3.0
- **deps-dev**: bump ruff from 0.11.13 to 0.12.12
- **deps-dev**: bump google-adk from 1.3.0 to 1.4.1
- **deps**: bump litellm from 1.72.6.post1 to 1.72.6.post2
- **deps-dev**: bump packaging from 24.2 to 25.0

### fix

- **docs**: replace HTML entities in completer.md to fix MDX parsing error
- **docs**: replace HTML entities in completer.md to fix MDX parsing error

### ✅🤡🧪 Tests

- **google-adk**: removing test google-adk
- **Tests**: add new tests for the cli and fixed a typo

### 💄🚸 UI & UIX

- **adding-tui**: add a tui for an interactive experience with the terminal

### 💚👷 CI & Build

- **Codecov**: Omitting tui from the pyproject
- **codecov**: testing codecov
- **Minor**: Minor fix on for codecov
- **removing-cloudflare**: Removing cloudflare from the deployment

### 📝💡 Documentation

- **Update-the-documentation**: fixing deployment of documentation
- **Update-the-documentation**: fixing deployment of documentation

## v0.2.5 (2025-06-20)

### bump

- **deps-dev**: bump pytest-asyncio from 0.23.8 to 1.0.0
- **deps-dev**: bump openapi-python-client from 0.24.3 to 0.25.0
- **deps-dev**: bump google-adk from 0.5.0 to 1.3.0
- **deps**: bump requests from 2.32.3 to 2.32.4
- **deps-dev**: bump commitizen from 4.8.0 to 4.8.3

### ✅🤡🧪 Tests

- **testing**: increased coverage for  testings up to 55%

### 💚👷 CI & Build

- **deploy**: fixing cloudflare deployment
- **deploy**: fixing cloudflare deployment
- **deploy**: ffixing deployment in cloudflare
- **deployment**: fixing deployment of docs in cloudflare

### 📌➕⬇️➖⬆️ Dependencies

- **commitizen**: update commitizen
- **commitizen**: update

### 📝💡 Documentation

- **logo**: adding images and logs
- **logo**: adding images and logs
- **documentation**: adding documentation
- **documentation**: adding documentation
- **docs**: add documentation
- **docs**: fixing poetry lock
- **docs**: resolving conflicts
- **documentation**: add docs
- **documentation**: adding documentation
- **docs**: add documentation

### 🔐🚧📈✏️💩👽️🍻💬🥚🌱🚩🥅🩺 Others

- **typo**: better example for google adk

### 🔖 bump

- **cli**: added cli to improve usage

### 🔧🔨📦️ Configuration, Scripts, Packages

- resolve GitHub Actions npm caching issue by including package-lock.json

## v0.2.4 (2025-05-22)

### 🐛🚑️ Fixes

- **versioning**: minor version update

### ✅🤡🧪 Tests

- **testing**: increased coverage for  testings up to 55%

### 📌➕⬇️➖⬆️ Dependencies

- **commitizen**: minor fixes

## v0.2.3 (2025-05-21)

### 🐛🚑️ Fixes

- **minor**: url for generator
- **ruff**: linting

### ♻️ Refactorings

- **api**: adding judge and generator within the api

### ✅🤡🧪 Tests

- **coverage**: reduced the minimum coverage to 40

## v0.2.2 (2025-05-21)

### ♻️ Refactorings

- **api**: adding judge and generator within the api

## v0.2.1 (2025-05-19)

### 🐛🚑️ Fixes

- **generator**: generator available with the api
- **generator**: generator available with the api

## v0.2.0 (2025-05-18)

### ✨ Features

- **initial**: first commit

### 🐛🚑️ Fixes

- **testing**: add tests and removed asynch calls
- **testing**: add tests and removed asynch calls
- **token**: removed token
- **API**: Add api key to the hackagent class as it was missing
- **google-adk**: google-adk moved to the dev depends

### bump

- **deps-dev**: bump commitizen from 4.7.0 to 4.7.1

### ✅🤡🧪 Tests

- **coverage**: test coverage more than 60%

### 💚👷 CI & Build

- **publich**: publish without tests
- **PyPi**: Add first release to PyPI

### 📌➕⬇️➖⬆️ Dependencies

- **dep**: update dependency
- **lock**: update poetry lock
- **litellm**: litellm v1.69.2

### 📝💡 Documentation

- **README.md**: update readme and url

### 🔧🔨📦️ Configuration, Scripts, Packages

- **tag**: tag versioning

### 🚨 Linting

- **minor**: lynting
