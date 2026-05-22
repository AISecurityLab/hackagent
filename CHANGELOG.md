## v0.10.1 (2026-05-22)

### fix

- replace hardcoded OpenAI model defaults with local Ollama defaults
- resolve top-level 'judge' dict before falling back to gpt-4-0613 default
- move examples/ inside hackagent package for correct wheel packaging

## v0.10.0 (2026-05-22)

### ✨ Features

- possibility to enable or disable thinking with ollama
- possibility to enable or disable thinking with ollama

### 🐛🚑️ Fixes

- abort attack if non-default category classifier model is not s…
- fixed integration tests
- abort attack if non-default category classifier model is not specified and the default model is not present in ollama

### bump

- **deps-dev**: bump pre-commit from 4.5.1 to 4.6.0
- **deps**: bump click from 8.1.8 to 8.4.0
- **deps-dev**: bump pytest-rerunfailures from 16.1 to 16.2
- **deps-dev**: bump packaging from 26.0 to 26.2
- version 0.9.0 → 0.9.1
- **deps-dev**: bump commitizen from 4.13.10 to 4.16.0

### fix

- move examples/ inside hackagent package for correct wheel packaging
- normalize TAP judge scores to consistent 1-10 scale
- pass TAP success_threshold to coordinator finalize_all_goals
- normalize TAP judge scores to a consistent 1-10 scale

### 🫥 fixup

- fixed merge conflict on tag bump

## v0.9.1 (2026-05-21)

## v0.9.0 (2026-05-15)

## v0.8.0 (2026-05-14)

### ✨ Features

- Improved attacks, updated documentation and dashboard
- add attack configuration flow to TUI
- add attack configuration flow to TUI

### 🐛🚑️ Fixes

- correct api configuration for all roles in all attacks in tui

### build

- **deps**: bump authlib from 1.6.6 to 1.6.9
- **deps**: bump authlib from 1.6.6 to 1.6.9

### bump

- **deps-dev**: bump transformers from 4.57.6 to 5.5.4
- **deps**: bump litellm from 1.83.0 to 1.83.10
- **deps**: bump textual from 8.2.1 to 8.2.4
- **deps-dev**: bump pytest from 9.0.2 to 9.0.3
- **deps-dev**: bump google-adk from 1.28.0 to 1.31.0
- **deps**: bump rich from 14.3.3 to 15.0.0
- **deps-dev**: bump commitizen from 4.13.9 to 4.13.10
- **deps**: bump click from 8.3.1 to 8.3.2
- **deps-dev**: bump mcp from 1.26.0 to 1.27.0
- **deps-dev**: bump requests from 2.32.5 to 2.33.1
- **deps-dev**: bump ruff from 0.15.8 to 0.15.9
- **deps**: bump openai from 2.29.0 to 2.30.0
- **deps-dev**: bump google-adk from 1.27.3 to 1.28.0

### feat

- propagate adapter/execution errors in AutoDAN-Turbo results
- propagate adapter/execution errors in TAP attack results
- propagate adapter/execution errors in PAP attack results
- propagate adapter/execution errors in PAIR attack results

### fix

- propagate adapter/execution errors to dashboard instead of masking as failed attacks
- **advprefix**: propagate errors to results instead of marking as mitigated  Error rows (e.g. timeouts) were silently lost through the evaluation pipeline and finalized as FAILED_JAILBREAK ("Mitigated") instead of ERROR_AGENT_RESPONSE.  Root causes fixed: - completions.py: propagate the normalized 'error' key so   _detect_error_indices can identify error rows downstream - evaluation.py: detect/mark error rows before judge evaluation;   preserve error rows through NLL filtering, aggregation, and   selection so they reach finalize_all_goals with is_error=True - sync.py: skip is_error rows in sync_evaluation_to_server so the   coordinator's ERROR_AGENT_RESPONSE is not overwritten by   FAILED_JAILBREAK
- propagate BoN adapter errors as ERROR_AGENT_RESPONSE in dashboard
- propagate adapter/execution errors instead of masking them as failed attacks
- prevent orchestrator re-evaluation from zeroing jailbreak counts

### refactor

- unify dashboard labels, colors, and error reporting

### 📝💡 Documentation

- fixed documentation
- fixed documentation
- documentation update

## v0.7.0 (2026-05-14)

### ✨ Features

- metrics results saving in json
- judge metrics visualization on local dashboard, strictness is now 1-avg(ASR)
- **evaluator**: metrics added on local dashbaord
- general bug fixing and improvement for all the attacks and the local dashboard
- Local dashboard now works both in remote and in local mode.
- Adding local dashboard features
- Automatic Ollama setup with 'hackagent examples ollama'
- Added Ollama demo
- Added CipherCheat attack
- Added CipherCheat attack
- Added CipherChat attack
- Added PAP attack
- Updated attack list in TUI
- H4RM3L attack added

### 🐛🚑️ Fixes

- **evaluator**: reformated file
- **evaluator**: safely handle non-dict rows and update orchestrator test
- fixed bugs on all the attacks, local dashboard improved, retry mechanism implemented in openai requests
- Fixed documentation
- Fixed documentation
- Bug fixing for PAIR and baseline
- Fixed remote fetching for local dashboard
- Fixed TAP test
- Fixed TAP test
- Unit tests fixed
- Fixed API key init error
- Allow for empty API key
- Added CipherChat attack to TUI
- Fixed tests that made pytest loop
- Fixed result ordering, date and fetching. Added "Attack" column with the type of the attack
- Fixed result ordering, date and fetching. Added "Attack" column with the type of the attack
- Fixed startup error for local web app
- **docs**: fixing tests
- **docs**: can we please fix the docs
- **docs**: compilation of documentation
- **docs**: fixing docs error
- **docs**: building docs

### ♻️ Refactorings

- **standardize-attack-config**: standardization for each attack configuration

### bump

- **deps**: bump datasets from 4.8.3 to 4.8.4
- **deps-dev**: bump ruff from 0.15.7 to 0.15.8
- **deps**: bump litellm from 1.82.6 to 1.83.0
- **deps**: bump textual from 8.1.1 to 8.2.1
- **deps-dev**: bump pytest-cov from 7.0.0 to 7.1.0
- **deps-dev**: bump anyio from 4.12.1 to 4.13.0
- **deps-dev**: bump google-adk from 1.27.1 to 1.27.3
- **deps**: bump litellm from 1.82.4 to 1.82.6
- **deps**: bump nicegui from 3.8.0 to 3.9.0
- **deps-dev**: bump ruff from 0.15.6 to 0.15.7
- **deps**: bump datasets from 4.8.2 to 4.8.3
- **deps**: bump openai from 2.28.0 to 2.29.0
- **deps-dev**: bump google-adk from 1.27.0 to 1.27.1
- **deps**: bump datasets from 4.7.0 to 4.8.2
- **deps**: bump litellm from 1.82.1 to 1.82.3
- **deps**: bump pypdf from 6.7.5 to 6.9.1

### ci

- split tests into focused jobs and merge coverage
- scope test-matrix and test-quick to tests/unit/ only

### fix

- **ci**: use find instead of glob to locate .coverage files
- **ci**: include hidden .coverage files in upload artifacts
- **ci**: correct coverage artifact glob path
- use isinstance(next_page, (str, AnyUrl)) to avoid infinite pagination loop
- correct AnyUrl pagination check in RemoteBackend list methods
- **tests**: update test_update_result_status_function to use backend kwarg
- use backend.update_result() in baseline legacy evaluation sync path
- **e2e**: skip auth test when HACKAGENT_API_BASE_URL not explicitly set
- update attack techniques to use _backend config key and Tracker(backend=...)
- **tests**: pass backend=RemoteBackend(client) to AgentRouter in integration tests
- **remote**: use .next instead of .next_ on PaginatedAgentList
- **docs**: set markdown format:detect so .md files skip MDX parsing
- **docs**: use HTML entities instead of backslash escapes for MDX v3 compatibility
- **ci**: ruff format, F821 undefined name, F841 unused variable

### refactor

- standardize attack config naming

### style

- ruff format remote.py
- remove unused patch import from test_evaluation_updates
- fix ruff formatting in bon/generation.py and pap/generation.py
- **tests**: apply ruff formatting to integration adapter tests

### ✅🤡🧪 Tests

- Fixed test_tap.py
- **docs**: fixing docs tests

### 🎨🏗️ Style & Architecture

- reformatting
- formatting
- Fixed tests and linting
- **local-api**: local version of the storage that does not require api connection
- **local-api**: local version of the storage that does not require api connection

### 💚👷 CI & Build

- Fixed integration tests

### 📝💡 Documentation

- **build**: fixing build error

### 🔥⚰️ Clean up

- Removed e2e PAIR test
- Removed unnecessary tests
- Removed original codebase of PAP

### 🫥 fixup

- Fixed merge

## v0.6.0 (2026-03-14)

### ✨ Features

- Added BoN attack
- Added BoN attack
- Added AutoDan-Turbo, fixed goal parallelization for all attacks
- removed dublicated function
- removed dublicated function
- removed dublicated function
- removed formated error from  the file after adding tests
- formated the files after adding tests
- add tests and fix metrics calculations
-  reformated all files
-  reformated
-  update init
- add new metrics with exception handling and ASR majority vote
- Added AutoDan-Turbo, fixed goal parallelization for all attacks
- Added AutoDAN-turbo
- TAP attack added
- TAP attack added

### 🐛🚑️ Fixes

- **tests**: fixing tests
- **API**: fixing api connection
- **merge-with-main**: testing the pull request
- Now score columns automatically adapt on presence or absence of a certain judge type
- **tests**: fixing tests
- **embeddings**: fixing the embeddings error
- Fixed parallelization for advprefix and flipattack + documentation + latency logging
- **vllm**: adding vllm as additional inference endpoint
- **tracker**: Tracking the results and traces through the api
- **jailbreak**: adding jailbreak example
- Added UTF8 documentation support for Windows

### ♻️ Refactorings

- **api**: refactoring api to make use of pydantic and removed all list of models

### ⚡️ Performance

- **parallelization**: parallelization for attacks generation in batches
- **parallelization**: parallelization for attacks generation in batches

### bump

- **deps-dev**: bump google-adk from 1.26.0 to 1.27.0
- **deps-dev**: bump ruff from 0.15.5 to 0.15.6
- **deps**: bump openai from 2.26.0 to 2.28.0
- **deps**: bump datasets from 4.6.1 to 4.7.0
- **deps-dev**: bump openapi-python-client from 0.28.2 to 0.28.3
- **deps**: bump textual from 8.0.2 to 8.1.1
- **deps**: bump litellm from 1.82.0 to 1.82.1
- **deps-dev**: bump ruff from 0.15.4 to 0.15.5
- **deps**: bump openai from 2.24.0 to 2.26.0
- **deps-dev**: bump transformers from 4.57.6 to 5.3.0
- **deps**: bump textual from 8.0.0 to 8.0.2
- **deps**: bump datasets from 4.6.0 to 4.6.1
- **deps**: bump litellm from 1.81.16 to 1.82.0
- **deps**: bump datasets from 4.5.0 to 4.6.0
- **deps-dev**: bump commitizen from 4.13.8 to 4.13.9
- **deps**: bump litellm from 1.81.14 to 1.81.16
- **deps-dev**: bump google-adk from 1.25.1 to 1.26.0
- **deps**: bump openai from 2.22.0 to 2.24.0
- **deps-dev**: bump ruff from 0.15.2 to 0.15.4
- **deps**: bump litellm from 1.81.13 to 1.81.14
- **deps**: bump openai from 2.21.0 to 2.22.0
- **deps-dev**: bump ruff from 0.15.1 to 0.15.2
- **deps-dev**: bump commitizen from 4.13.7 to 4.13.8
- **deps-dev**: bump flask from 3.1.2 to 3.1.3
- **deps**: bump rich from 14.3.2 to 14.3.3
- **deps-dev**: bump google-adk from 1.25.0 to 1.25.1
- **deps**: bump litellm from 1.81.12 to 1.81.13

### ✅🤡🧪 Tests

- **tests**: fixing tests
- **integration**: fixing integration tests
- **flipattack**: fix model_validate → from_dict and add _self to generation config
- **flipattack**: flipattack tests not passing
- **ci-cd**: fixing tests for windows
- **ci-cd**: fixing tests in ci-cd
- **integration**: fixing integration tests

### 💚👷 CI & Build

- Fixed lock

### 📝💡 Documentation

- **Comments**: Adding comments to the functions and documentation
- **Risks-profile**: Adding risk profiles within the documentation

### 🔥⚰️ Clean up

- -
- -
- **db_index**: db_index folder

## v0.5.0 (2026-02-17)

### ✨ Features

- **FlipAttack**: The FlipAttack technique was introduced.
- **FlipAttack**: The FlipAttack technique was introduced. It is also tested in the test folder

### 🐛🚑️ Fixes

- the error on the JSON serialization with the OpenAI SDK is fixed

### ♻️ Refactorings

- **generator-and-judge**: We add the RAG within our demo
- **generator-and-judge**: We add the RAG within our demo
- **Refactoring-attacks**: refactoring attacks code with folders for evaluator and generator

### build

- **deps**: bump urllib3 from 2.5.0 to 2.6.3
- **deps**: bump urllib3 from 2.5.0 to 2.6.3

### bump

- **deps**: bump litellm from 1.81.8 to 1.81.12
- **deps-dev**: bump ruff from 0.15.0 to 0.15.1
- **deps**: bump openai from 2.17.0 to 2.21.0
- **deps**: bump textual from 7.5.0 to 8.0.0
- **deps-dev**: bump commitizen from 4.13.5 to 4.13.7
- **deps-dev**: bump openapi-python-client from 0.28.1 to 0.28.2
- **deps-dev**: bump google-adk from 1.24.1 to 1.25.0
- **deps-dev**: bump ruff from 0.14.14 to 0.15.0
- **deps**: bump rich from 14.3.1 to 14.3.2
- **deps**: bump litellm from 1.81.5 to 1.81.8
- **deps-dev**: bump google-adk from 1.24.0 to 1.24.1
- **deps-dev**: bump mcp from 1.25.0 to 1.26.0
- **deps-dev**: bump google-adk from 1.23.0 to 1.24.0
- **deps**: bump openai from 2.16.0 to 2.17.0
- **deps-dev**: bump commitizen from 4.12.1 to 4.13.5
- **deps**: bump litellm from 1.81.1 to 1.81.5
- **deps**: bump textual from 7.4.0 to 7.5.0
- **deps**: bump openai from 2.15.0 to 2.16.0
- **deps**: bump rich from 14.2.0 to 14.3.1
- **deps**: bump textual from 7.3.0 to 7.4.0

### fix

- **tests**: fix JSON serialization issue
- **tests**: fix JSON serialization issue

### style

- apply ruff formatting

### ✅🤡🧪 Tests

- In examples\langchain\rag there is a test using an AdvPrefix attack with a RAG use case, using a custom LangChain-based endpoint with OpenAI interfaces
- In examples\langchain\rag there is a test showing an advprefix attack in a RAG scenario using a custom endpoint with LangChain based on OpenAI interfaces

### 📝💡 Documentation

- **Risks-profile**: Adding risk profiles within the documentation
- **Risks**: Adding risks and related vulnerabilities with profiles

### 🔥⚰️ Clean up

- removed test rag lmstudio script

### 🫥 fixup

- reformatted attack py

## v0.4.4 (2026-01-27)

### 🐛🚑️ Fixes

- **Google-ADK**: Error within the google adk tracer
- **minor**: google adk output
- **Google-ADK**: fixed the session creation
- **Google-ADK**: Error within the google adk tracer

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
