# Reuse Lab
Public demonstration: https://reuse-durability-lab.vercel.app/

Independent work sample about accepted fixes across changed task contexts, prepared for discussion around Bosch Rexroth Academy REF300188Y. It is not a Bosch product or evidence of an internal Bosch defect.

## Engineering question
When a reviewed fix is reused after a procedure or equipment condition changes, does its evidence still support the current task, and what does checking reuse cost?

Access, applicability, evidence sufficiency and actual task execution are separate outcomes. Paired 3D replay shows computed action snapshots. Editable tasks and presets run through the same engine. A deterministic assistant can inspect and explain; it cannot approve a fix.

## Local use
Python 3.10+; runtime uses the standard library.

    python server.py --port 8794

Open http://127.0.0.1:8794/ . The local server binds to loopback and stores its own SQLite records.

## Tests
    python -m unittest test_engine test_api

The original 41 engine, persistence and API tests passed. For browser checks, install the dev dependency and Chromium, start the server, then run:

    npm install
    npx playwright install chromium
    npm run test:browser

The separate network test, python test_public_api.py, checks public visitor isolation and source boundaries. Four checks passed. Deployed desktop/mobile browser workflows also passed.

## Negative results
Two saved synthetic sets each contain 280 tasks, four policies and assumed review costs.
Seed 42: full checks admitted 62 actions, but 24 failed execution; 38 completed valid tasks and 146 cases remained unresolved. A simpler semantic policy also completed 38 valid tasks.
Seed 17: full checks admitted 53 actions, with 11 execution failures, 42 valid completions and 141 unresolved cases.
The fixture and oracle share an authored specification. These are conformance experiments, not industrial validation or a demonstrated LLM/agent advantage.

## Deployment and Microsoft extension
The public adapter isolates temporary synthetic records by browser session. A restart or instance change can clear records; export evidence to retain it. Demo role selection is not authentication.
No Microsoft tenant records, credentials or private review data are part of the public deployment.

The separate Microsoft development environment demonstrated native human approval/rejection, revision blocking, duplicate protection, failed-write recovery and a reconciled Power BI snapshot.
Generic plugin source is in microsoft-extension/. Live exports, private connection bindings, auth tools, signing keys and private run histories are absent. This directory is not a one-command reproducible tenant solution.
The Microsoft proof uses one reviewer; production authorization, large-load concurrency and a second-environment import need additional validation. Four simultaneous native delivery submissions produced one decision and three AlreadyRecorded outcomes. Power BI is a saved snapshot.

## Attribution and limits
Research context: Guedria and Dommermuth, A Taxonomy and Reference Architecture for AI-enabled Industrial Knowledge Management, ECKM 2026: https://doi.org/10.34190/eckm.27.2.5093 .
The architecture is prior work. This contribution is the narrow, testable reuse boundary and retained negative results.
Vendored Three.js is MIT-licensed; see web/vendor/THREE_LICENSE.txt and PROVENANCE.json.
No real equipment, calibrated mechanics, OPC UA, Azure integration or safety certification is claimed.
