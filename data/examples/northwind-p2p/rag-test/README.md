# Sheldon RAG test pack

Files for testing Sheldon's answers from engagement documents end to end. The steps, questions and expected answers
are in [docs/05-testing/engagement-rag-test-plan.md](../../../../docs/05-testing/engagement-rag-test-plan.md).

- `upload-first/08_vendor_master_change_policy.pdf`: the policy, version 1.0. Approval within 4 business days, one
  call-back, frozen 5 days before a payment run.
- `upload-second/08_vendor_master_change_policy.pdf`: the same file name, version 2.0. Approval within 2 days, two
  call-backs, frozen 3 days. Upload it after the first to test that a new version replaces the old one.
- `generate_rag_test_files.py`: rebuilds both PDFs.

Upload these together with the files in `../source-documents/`.
