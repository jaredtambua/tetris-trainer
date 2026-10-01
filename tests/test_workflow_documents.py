"""Lightweight repository-document validation, included by make check."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'CONFIRMED', 'TO VERIFY', 'INTENTIONALLY OMITTED', 'PROJECT-SPECIFIC'}
REQUIRED_MECHANICS = {
    'Board dimensions / hidden rows', 'Tetromino geometry',
    'SRS+ rotations and kicks', 'Spawn behavior', 'Top-out / game-over behavior',
    'Seven-bag randomizer', 'Hold', 'Soft drop', 'Hard drop', 'Line clearing',
    'Gravity', 'Lock delay', 'Attack', 'Garbage', 'Combos', 'Back-to-back',
    'Spin detection / scoring', 'Opponent simulation',
}


def validate_register(text):
    """Validate the documented three-column mechanic table; reject drift."""
    lines = text.splitlines()
    header = '| Mechanic | Status | Current implementation / evidence boundary |'
    if lines.count(header) != 1:
        raise ValueError('expected exactly one mechanic register table')
    index = lines.index(header)
    if index + 1 >= len(lines) or lines[index + 1] != '| --- | --- | --- |':
        raise ValueError('missing mechanic table separator')
    mechanics = set()
    for line in lines[index + 2:]:
        if not line.startswith('|'):
            break
        columns = [part.strip() for part in line.split('|')[1:-1]]
        if len(columns) != 3 or not line.endswith('|') or not all(columns):
            raise ValueError('expected three nonempty mechanic table columns')
        mechanic, status, _ = columns
        if status not in STATUSES:
            raise ValueError(f'invalid status for {mechanic}: {status}')
        if mechanic in mechanics:
            raise ValueError(f'duplicate mechanic: {mechanic}')
        mechanics.add(mechanic)
    missing = REQUIRED_MECHANICS - mechanics
    if missing:
        raise ValueError(f'missing required mechanics: {sorted(missing)}')


class WorkflowDocumentTests(unittest.TestCase):
    def test_required_documents_exist_and_are_nonempty(self):
        for path in ('AGENTS.md', 'docs/TETRIO_RULESET.md', 'docs/DEVELOPMENT_WORKFLOW.md'):
            with self.subTest(path=path):
                document = ROOT / path
                self.assertTrue(document.is_file(), f'missing required document: {path}')
                self.assertTrue(document.read_text(encoding='utf-8').strip())

    def test_rule_register_statuses_and_coverage(self):
        validate_register((ROOT / 'docs/TETRIO_RULESET.md').read_text(encoding='utf-8'))

    def test_validator_rejects_invalid_status_missing_and_duplicate_rows(self):
        valid = (
            '| Mechanic | Status | Current implementation / evidence boundary |\n'
            '| --- | --- | --- |\n'
            + ''.join(f'| {name} | TO VERIFY | Evidence pending |\n'
                      for name in sorted(REQUIRED_MECHANICS))
        )
        row = next(line for line in valid.splitlines() if line.startswith('| Hold |'))
        variants = (
            valid.replace('| Hold | TO VERIFY |', '| Hold | VERIFIED |'),
            valid.replace(row + '\n', ''),
            valid.replace(row, row + '\n' + row),
            valid.replace(row, '| Hold | TO VERIFY | |'),
            valid.replace('| Mechanic | Status |', '| Mechanic | Evidence |'),
        )
        for index, invalid in enumerate(variants):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    validate_register(invalid)


if __name__ == '__main__':
    unittest.main()
