# Archive, Restore, Delete, and Recover

## Purpose

modelctl separates storage management from destructive lifecycle management.

The key distinction is:

* `archive` / `restore` are reversible storage operations.
* `delete` / `recover` are destructive lifecycle operations with recovery metadata.

This avoids using one vague concept such as "rollback" for different behaviours.

---

## Archive

`archive` moves a model file out of active model storage into archive storage.

Primary use case:

* Save active disk space.
* Keep the model available for later restoration.
* Avoid bloating the active model set.
* Preserve the ability to bring the model back without redownloading.

Default behaviour:

* Move the model file from active storage to archive storage.
* Preserve alias/router configuration by default.
* Do not disable aliases unless explicitly requested.
* Write enough movement metadata to support restore.

By default, archive should not destroy router configuration because the user may only be archiving to save space.

Optional behaviour:

* `--disable-aliases` may disable only the aliases affected by the archived model.
* Any alias change must be previewed before apply.
* Alias changes must be limited to aliases directly associated with the archived model.

Archive must not:

* Delete the model file permanently.
* Remove unrelated aliases.
* Rewrite unrelated router configuration.
* Disable all viable fallback models.
* Pretend that restoring the full old router configuration is safe.

---

## Restore

`restore` is the opposite of `archive`.

Preferred command name:

* `restore`

Optional alias later:

* `unarchive`

Primary use case:

* Move an archived model back into active model storage.

Default behaviour:

* Move the archived model file back to its original active location.
* Preserve current router configuration.
* Re-enable aliases only if they were explicitly disabled by the archive operation and if doing so is safe.
* Detect conflicts before applying.

Restore must check:

* The archived model file exists.
* The original active path is available or conflict-free.
* The restore operation will not overwrite a newer file without explicit confirmation.
* Any alias reactivation affects only aliases that were recorded as part of the original archive operation.

Restore must not:

* Replace the whole router configuration file.
* Undo unrelated changes made after archive.
* Recreate unrelated aliases.
* Modify aliases unless the archive operation explicitly changed them and restore metadata confirms it.

---

## Delete

`delete` is the destructive lifecycle operation.

Primary use case:

* Remove a model file from managed storage.
* Remove or disable only the relevant alias/router configuration.
* Save recovery metadata so configuration can be reconstructed later if the model is redownloaded.

Delete should create a recovery manifest in JSON.

The recovery manifest should include:

* Deleted model path.
* Model filename.
* Model size and hash where available.
* Source metadata where available.
* Affected aliases only.
* Affected sections only.
* Removed alias configuration only.
* Delete timestamp.
* Reason or user note where provided.
* Redownload source where known.
* Relevant runtime/profile metadata.

Delete must not save or rely on a full router configuration restore as the default recovery model.

Delete must not remove unrelated router configuration.

Delete must preview:

* Files to be deleted.
* Aliases to be removed or disabled.
* Sections affected.
* Recovery manifest path.
* Whether source metadata is sufficient for later recovery.

---

## Recover

`recover` uses a delete recovery manifest to help reconstruct model configuration after deletion.

Primary use case:

* A model was deleted.
* The user later redownloaded it or restored the file manually.
* modelctl uses the saved recovery manifest to recreate only the relevant aliases and sections.

Recover should:

* Read the delete recovery manifest.
* Check whether the model file exists again.
* Recreate only the affected aliases/sections.
* Detect conflicts with current router configuration.
* Preserve unrelated changes made after delete.
* Preview the recovery operation before applying.

Recover must not:

* Restore the entire old router configuration.
* Erase unrelated aliases added later.
* Overwrite current aliases without conflict detection.
* Assume that the model file has been redownloaded unless it can verify it.

---

## Why rollback is not the right default concept

`rollback` sounds like it reverses everything to a previous state.

That is dangerous for modelctl because the user may have made valid changes after archive or delete, such as:

* Adding a new model.
* Changing alias settings.
* Updating context or runtime parameters.
* Reorganising sections.
* Disabling a different model.
* Changing fallback strategy.

For this reason:

* Archive should be reversed with `restore`.
* Delete should be repaired with `recover`.
* Full configuration rollback should be treated as high-risk recovery only.

A full router configuration restore must require explicit override and a clear preview because it may erase unrelated later changes.

---

## Product Rule

Archive/restore and delete/recover must be surgical.

They must operate only on:

* The relevant model file.
* The relevant aliases.
* The relevant sections.
* The relevant recovery metadata.

They must not blindly restore the whole router configuration by default.
