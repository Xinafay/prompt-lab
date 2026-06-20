# Prompt Preview Design

## Goal

Add an optional prepare-preview-accept-send workflow for run, validation, judge, and proposal prompts so prompts that may exceed provider limits can be inspected before any LLM request is sent.

## Scope

The existing workflow actions remain unchanged:

- Run version
- Validate active run
- Judge active run
- Generate proposal

Each action gains a secondary preview action. Preview actions render the prompts using the same backend inputs and prompt builders as the live action, but do not start workflow jobs, call LLMs, or write runtime artifacts.

## Backend

Add prompt preview response models to `backend/prompt_lab/api.py`:

- `PromptPreviewItem` contains prompt text, prompt kind, display title, target model, optional case id, optional repeat index, optional validator id, character count, and word count.
- `PromptPreviewResponse` contains the workflow kind, prompt items, and optional warnings.

Add four preview endpoints next to the existing workflow endpoints:

- `POST /api/experiments/{experiment_id}/versions/{version}/runs/preview-prompts`
- `POST /api/experiments/{experiment_id}/versions/{version}/validations/preview-prompts`
- `POST /api/experiments/{experiment_id}/versions/{version}/judgments/preview-prompts`
- `POST /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal/preview-prompts`

Run preview renders the experiment prompt for every case and repeat using the existing Jinja renderer and materialized case context. For Pydantic outputs, the rendered prompt must preserve literal `<<MODEL>>`; schema replacement remains owned by structured generation and is not performed during preview.

Validation preview builds LLM questionnaire validator prompts for the latest validated run batch using `build_llm_validator_prompt`. Automatic validators do not produce LLM prompts and are excluded from preview. If the total prompt count would exceed `100`, preview still covers every case and every LLM validator, but only for the first repeat available for each case. The response includes a warning that additional repeats were hidden because the preview is too large.

Judge preview uses `build_judge_prompt` with the latest completed validation batch and the same validation evidence used by the real judgment action.

Proposal preview uses `build_proposal_prompt` with the selected review's judgment, saved decisions, human notes, validation context, current prompt, and model source.

## Frontend

Add `PromptPreviewResponse` and `PromptPreviewItem` types in `frontend/src/types.ts`, and API helpers in `frontend/src/api.ts`.

Add a reusable full-page `PromptPreviewModal` component. It receives a preview response and two callbacks:

- `onAccept`: closes the modal and invokes the existing workflow action.
- `onReject`: closes the modal without sending anything.

The modal displays any warnings first, then prompt cards in order. Each card shows the title, model, available case/repeat/validator metadata, character count, word count, and a preformatted prompt body. The footer stays visible with secondary `Reject` and primary `Accept` buttons.

Wire secondary `Preview prompts` buttons into:

- the workflow toolbar for run preview
- `ValidationView` for validation preview
- `ReviewView` for judge preview
- `ProposalView` for proposal preview

Disable preview buttons under the same prerequisites as their corresponding send action. Accept reuses the current live or dry-run mode by calling the existing action handler.

## Error Handling

Preview endpoints return the same prerequisite errors as their workflow actions, such as missing runs, missing validation, dirty client state blocked in the UI, or missing review decisions. Frontend errors are shown through the existing workflow message area.

## Testing

Backend tests cover:

- run preview renders all case/repeat prompts and preserves `<<MODEL>>`
- validation preview excludes automatic validators and applies the repeat trimming rule while preserving all cases and LLM validators
- judge preview returns the built judgment prompt without creating review artifacts
- proposal preview returns the built proposal prompt without creating proposal artifacts

Frontend tests cover:

- prompt preview modal renders prompts, metadata, counts, warnings, and accept/reject controls
- API helper paths are correct
- workflow handlers open preview and accept invokes the existing action path

Manual UI verification uses the running app with `demo-string` and the in-app browser on the proposal tab.
