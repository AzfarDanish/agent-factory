# Tests

## Test Strategy

| Layer | Location | Dependencies | Run Command |
|---|---|---|---|
| Unit | Co-located with source (e.g. `message_test.py` beside `message.py`) | None | `pytest src/ -k unit` |
| Integration | `tests/test_*_integration.py` | File queues, mock API servers | `pytest tests/` |
| End-to-end | `tests/test_full_pipeline.py` | Real queues, real APIs (opt-in) | `pytest tests/ -m e2e` |

## Fixtures

Shared fixtures in `conftest.py`:

- `temp_file_queue`: Temporary directory with file-based queues
- `mock_deepseek`: HTTP mock for DeepSeek API
- `mock_gpt_image`: HTTP mock for GPT Image 1 API
- `sample_request`: Valid coloring request dict
- `valid_message`: Complete message envelope dict

## Fixture Data

Test data lives in `tests/fixtures/`:

| Directory | Contents |
|---|---|
| `requests/` | Sample valid and invalid coloring requests (JSON) |
| `responses/` | Sample API responses from DeepSeek and GPT |
| `images/` | Sample output images for storage tests |

## Running Tests

```bash
# All tests
pytest

# Unit only (fast)
pytest -m unit

# Integration only
pytest -m integration

# With coverage
pytest --cov=src
```
