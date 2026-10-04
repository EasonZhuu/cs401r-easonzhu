# Lab 2 — Apply Log Provenance

`lab2-extend-output.txt` retains the original Task 1 Terraform transcript,
including SageMaker Domain creation. The subsequent sections consolidate
actual crawler creation and user terminal output from the same lab session.
The headings identify the source; the Terraform output below each heading
is preserved, with terminal whitespace normalized.

The original full apply transcripts for initial transform-job and Feature
Group creation were not found in the available saved output. Their later
configuration, successful runs and stored data are recorded by the AWS
verifier and data audit. These checks do not reconstruct a missing historical
Terraform transcript. The final network-alignment and LF synchronization
applies were recorded directly in the combined log.

`lab2-creation-api-evidence.json` contains three genuine CloudTrail creation
events. Their user agents identify Terraform and the AWS provider. Sensitive
identity and network fields were omitted. These API events supplement the
current verification evidence but do not replace the missing terminal logs.

No resources were destroyed and recreated to manufacture historical evidence.
