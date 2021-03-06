from mock import patch
from subprocess import Popen
from textwrap import dedent
from StringIO import StringIO
from lxml import etree
from diff_cover.violations_reporter import XmlCoverageReporter, Violation, \
    Pep8QualityReporter, PylintQualityReporter, QualityReporterError
from diff_cover.tests.helpers import unittest


class XmlCoverageReporterTest(unittest.TestCase):

    MANY_VIOLATIONS = set([Violation(3, None), Violation(7, None),
                           Violation(11, None), Violation(13, None)])
    FEW_MEASURED = set([2, 3, 5, 7, 11, 13])

    FEW_VIOLATIONS = set([Violation(3, None), Violation(11, None)])
    MANY_MEASURED = set([2, 3, 5, 7, 11, 13, 17])

    ONE_VIOLATION = set([Violation(11, None)])
    VERY_MANY_MEASURED = set([2, 3, 5, 7, 11, 13, 17, 23, 24, 25, 26, 26, 27])

    def test_violations(self):

        # Construct the XML report
        file_paths = ['file1.py', 'subdir/file2.py']
        violations = self.MANY_VIOLATIONS
        measured = self.FEW_MEASURED
        xml = self._coverage_xml(file_paths, violations, measured)

        # Parse the report
        coverage = XmlCoverageReporter(xml)

        # Expect that the name is set
        self.assertEqual(coverage.name(), "XML")

        # By construction, each file has the same set
        # of covered/uncovered lines
        self.assertEqual(violations, coverage.violations('file1.py'))
        self.assertEqual(measured, coverage.measured_lines('file1.py'))

        # Try getting a smaller range
        result = coverage.violations('subdir/file2.py')
        self.assertEqual(result, violations)

        # Once more on the first file (for caching)
        result = coverage.violations('file1.py')
        self.assertEqual(result, violations)

    def test_two_inputs_first_violate(self):

        # Construct the XML report
        file_paths = ['file1.py']

        violations1 = self.MANY_VIOLATIONS
        violations2 = self.FEW_VIOLATIONS

        measured1 = self.FEW_MEASURED
        measured2 = self.MANY_MEASURED

        xml = self._coverage_xml(file_paths, violations1, measured1)
        xml2 = self._coverage_xml(file_paths, violations2, measured2)

        # Parse the report
        coverage = XmlCoverageReporter([xml, xml2])

        # By construction, each file has the same set
        # of covered/uncovered lines
        self.assertEqual(
            violations1 & violations2,
            coverage.violations('file1.py')
        )

        self.assertEqual(
            measured1 | measured2,
            coverage.measured_lines('file1.py')
        )

    def test_two_inputs_second_violate(self):

        # Construct the XML report
        file_paths = ['file1.py']

        violations1 = self.MANY_VIOLATIONS
        violations2 = self.FEW_VIOLATIONS

        measured1 = self.FEW_MEASURED
        measured2 = self.MANY_MEASURED

        xml = self._coverage_xml(file_paths, violations1, measured1)
        xml2 = self._coverage_xml(file_paths, violations2, measured2)

        # Parse the report
        coverage = XmlCoverageReporter([xml2, xml])

        # By construction, each file has the same set
        # of covered/uncovered lines
        self.assertEqual(
            violations1 & violations2,
            coverage.violations('file1.py')
        )

        self.assertEqual(
            measured1 | measured2,
            coverage.measured_lines('file1.py')
        )

    def test_three_inputs(self):

        # Construct the XML report
        file_paths = ['file1.py']

        violations1 = self.MANY_VIOLATIONS
        violations2 = self.FEW_VIOLATIONS
        violations3 = self.ONE_VIOLATION

        measured1 = self.FEW_MEASURED
        measured2 = self.MANY_MEASURED
        measured3 = self.VERY_MANY_MEASURED

        xml = self._coverage_xml(file_paths, violations1, measured1)
        xml2 = self._coverage_xml(file_paths, violations2, measured2)
        xml3 = self._coverage_xml(file_paths, violations3, measured3)

        # Parse the report
        coverage = XmlCoverageReporter([xml2, xml, xml3])

        # By construction, each file has the same set
        # of covered/uncovered lines
        self.assertEqual(
            violations1 & violations2 & violations3,
            coverage.violations('file1.py')
        )

        self.assertEqual(
            measured1 | measured2 | measured3,
            coverage.measured_lines('file1.py')
        )

    def test_different_files_in_inputs(self):

        # Construct the XML report
        xml_roots = [
            self._coverage_xml(['file.py'], self.MANY_VIOLATIONS, self.FEW_MEASURED),
            self._coverage_xml(['other_file.py'], self.FEW_VIOLATIONS, self.MANY_MEASURED)
        ]

        # Parse the report
        coverage = XmlCoverageReporter(xml_roots)

        self.assertEqual(self.MANY_VIOLATIONS, coverage.violations('file.py'))
        self.assertEqual(self.FEW_VIOLATIONS, coverage.violations('other_file.py'))

    def test_empty_violations(self):
        """
        Test that an empty violations report is handled properly
        """

        # Construct the XML report
        file_paths = ['file1.py']

        violations1 = self.MANY_VIOLATIONS
        violations2 = set()

        measured1 = self.FEW_MEASURED
        measured2 = self.MANY_MEASURED

        xml = self._coverage_xml(file_paths, violations1, measured1)
        xml2 = self._coverage_xml(file_paths, violations2, measured2)

        # Parse the report
        coverage = XmlCoverageReporter([xml2, xml])

        # By construction, each file has the same set
        # of covered/uncovered lines
        self.assertEqual(
            violations1 & violations2,
            coverage.violations('file1.py')
        )

        self.assertEqual(
            measured1 | measured2,
            coverage.measured_lines('file1.py')
        )

    def test_no_such_file(self):

        # Construct the XML report with no source files
        xml = self._coverage_xml([], [], [])

        # Parse the report
        coverage = XmlCoverageReporter(xml)

        # Expect that we get no results
        result = coverage.violations('file.py')
        self.assertEqual(result, set([]))

    def _coverage_xml(self, file_paths, violations, measured):
        """
        Build an XML tree with source files specified by `file_paths`.
        Each source fill will have the same set of covered and
        uncovered lines.

        `file_paths` is a list of path strings
        `line_dict` is a dictionary with keys that are line numbers
        and values that are True/False indicating whether the line
        is covered

        This leaves out some attributes of the Cobertura format,
        but includes all the elements.
        """
        root = etree.Element('coverage')
        packages = etree.SubElement(root, 'packages')
        classes = etree.SubElement(packages, 'classes')

        violation_lines = set(violation.line for violation in violations)

        for path in file_paths:

            src_node = etree.SubElement(classes, 'class')
            src_node.set('filename', path)

            etree.SubElement(src_node, 'methods')
            lines_node = etree.SubElement(src_node, 'lines')

            # Create a node for each line in measured
            for line_num in measured:
                is_covered = line_num not in violation_lines
                line = etree.SubElement(lines_node, 'line')

                hits = 1 if is_covered else 0
                line.set('hits', str(hits))
                line.set('number', str(line_num))

        return root


class Pep8QualityReporterTest(unittest.TestCase):

    def tearDown(self):
        """
        Undo all patches
        """
        patch.stopall()

    def test_quality(self):

        # Patch the output of `pep8`
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = (
            '\n' + dedent("""
                ../new_file.py:1:17: E231 whitespace
                ../new_file.py:3:13: E225 whitespace
                ../new_file.py:7:1: E302 blank lines
            """).strip() + '\n', ''
        )

        # Parse the report
        quality = Pep8QualityReporter('pep8', [])

        # Expect that the name is set
        self.assertEqual(quality.name(), 'pep8')

        # Measured_lines is undefined for
        # a quality reporter since all lines are measured
        self.assertEqual(quality.measured_lines('../new_file.py'), None)

        # Expect that we get the right violations
        expected_violations = [
            Violation(1, 'E231 whitespace'),
            Violation(3, 'E225 whitespace'),
            Violation(7, 'E302 blank lines')
        ]

        self.assertEqual(expected_violations, quality.violations('../new_file.py'))

    def test_no_quality_issues_newline(self):

        # Patch the output of `pep8`
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = ('\n', '')

        # Parse the report
        quality = Pep8QualityReporter('pep8', [])
        self.assertEqual([], quality.violations('file1.py'))

    def test_no_quality_issues_emptystring(self):

        # Patch the output of `pep8`
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = ('', '')

        # Parse the report
        quality = Pep8QualityReporter('pep8', [])
        self.assertEqual([], quality.violations('file1.py'))

    def test_quality_error(self):

        # Patch the output of `pep8`
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = ("", 'whoops')

        # Parse the report
        quality = Pep8QualityReporter('pep8', [])

        # Expect that the name is set
        self.assertEqual(quality.name(), 'pep8')

        self.assertRaises(QualityReporterError, quality.violations, 'file1.py')

    def test_no_such_file(self):
        quality = Pep8QualityReporter('pep8', [])

        # Expect that we get no results
        result = quality.violations('')
        self.assertEqual(result, [])

    def test_no_python_file(self):
        quality = Pep8QualityReporter('pep8', [])
        file_paths = ['file1.coffee', 'subdir/file2.js']
        # Expect that we get no results because no Python files
        for path in file_paths:
            result = quality.violations(path)
            self.assertEqual(result, [])

    def test_quality_pregenerated_report(self):

        # When the user provides us with a pre-generated pep8 report
        # then use that instead of calling pep8 directly.
        pep8_reports = [
            StringIO('\n' + dedent("""
                path/to/file.py:1:17: E231 whitespace
                path/to/file.py:3:13: E225 whitespace
                another/file.py:7:1: E302 blank lines
            """.encode('utf-8')).strip() + '\n'),

            StringIO('\n' + dedent(u"""
                path/to/file.py:24:2: W123 \u9134\u1912
                another/file.py:50:1: E302 blank lines
            """.encode('utf-8')).strip() + '\n'),
        ]

        # Parse the report
        quality = Pep8QualityReporter('pep8', pep8_reports)

        # Measured_lines is undefined for
        # a quality reporter since all lines are measured
        self.assertEqual(quality.measured_lines('path/to/file.py'), None)

        # Expect that we get the right violations
        expected_violations = [
            Violation(1, u'E231 whitespace'),
            Violation(3, u'E225 whitespace'),
            Violation(24, u'W123 \u9134\u1912')
        ]

        # We're not guaranteed that the violations are returned
        # in any particular order.
        actual_violations = quality.violations('path/to/file.py')

        self.assertEqual(len(actual_violations), len(expected_violations))
        for expected in expected_violations:
            self.assertIn(expected, actual_violations)


class PylintQualityReporterTest(unittest.TestCase):

    def tearDown(self):
        """
        Undo all patches.
        """
        patch.stopall()

    def test_no_such_file(self):
        quality = PylintQualityReporter('pylint', [])

        # Expect that we get no results
        result = quality.violations('')
        self.assertEqual(result, [])

    def test_no_python_file(self):
        quality = PylintQualityReporter('pylint', [])
        file_paths = ['file1.coffee', 'subdir/file2.js']
        # Expect that we get no results because no Python files
        for path in file_paths:
            result = quality.violations(path)
            self.assertEqual(result, [])

    def test_quality(self):
        # Patch the output of `pylint`
        _mock_communicate = patch.object(Popen, 'communicate').start()

        _mock_communicate.return_value = (
            dedent("""
            file1.py:1: [C0111] Missing docstring
            file1.py:1: [C0111, func_1] Missing docstring
            file1.py:2: [W0612, cls_name.func] Unused variable 'd'
            file1.py:2: [W0511] TODO: Not the real way we'll store usages!
            file1.py:579: [F0401] Unable to import 'rooted_paths'
            file1.py:113: [W0613, cache_relation.clear_pk] Unused argument 'cls'
            file1.py:150: [F0010] error while code parsing ([Errno 2] No such file or directory)
            file1.py:149: [C0324, Foo.__dict__] Comma not followed by a space
                self.peer_grading._find_corresponding_module_for_location(Location('i4x','a','b','c','d'))
            file1.py:162: [R0801] Similar lines in 2 files
            ==external_auth.views:1
            ==student.views:4
            import json
            import logging
            import random
            path/to/file2.py:100: [W0212, openid_login_complete] Access to a protected member
            """).strip(), ''
        )

        expected_violations = [
            Violation(1, 'C0111: Missing docstring'),
            Violation(1, 'C0111: func_1: Missing docstring'),
            Violation(2, "W0612: cls_name.func: Unused variable 'd'"),
            Violation(2, "W0511: TODO: Not the real way we'll store usages!"),
            Violation(579, "F0401: Unable to import 'rooted_paths'"),
            Violation(150, "F0010: error while code parsing ([Errno 2] No such file or directory)"),
            Violation(149, "C0324: Foo.__dict__: Comma not followed by a space"),
            Violation(162, "R0801: Similar lines in 2 files"),
            Violation(113, "W0613: cache_relation.clear_pk: Unused argument 'cls'")
        ]

        # Parse the report
        quality = PylintQualityReporter('pylint', [])

        # Expect that the name is set
        self.assertEqual(quality.name(), 'pylint')

        # Measured_lines is undefined for a
        # quality reporter since all lines are measured
        self.assertEqual(quality.measured_lines('file1.py'), None)

        # Expect that we get violations for file1.py only
        # We're not guaranteed that the violations are returned
        # in any particular order.
        actual_violations = quality.violations('file1.py')
        self.assertEqual(len(actual_violations), len(expected_violations))
        for expected in expected_violations:
            self.assertIn(expected, actual_violations)

    def test_unicode(self):
        _mock_communicate = patch.object(Popen, 'communicate').start()

        # Test non-ascii unicode characters in the filename, function name and message
        _mock_communicate.return_value = (dedent(u"""
            file_\u6729.py:616: [W1401] Anomalous backslash in string: '\u5922'. String constant might be missing an r prefix.
            file.py:2: [W0612, cls_name.func_\u9492] Unused variable '\u2920'
        """).encode('utf-8'), '')

        quality = PylintQualityReporter('pylint', [])
        violations = quality.violations(u'file_\u6729.py')
        self.assertEqual(violations, [
            Violation(616, u"W1401: Anomalous backslash in string: '\u5922'. String constant might be missing an r prefix."),
        ])

        violations = quality.violations(u'file.py')
        self.assertEqual(violations, [Violation(2, u"W0612: cls_name.func_\u9492: Unused variable '\u2920'")])

    def test_unicode_continuation_char(self):
        _mock_communicate = patch.object(Popen, 'communicate').start()

        # Test a unicode continuation char, which pylint can produce (probably an encoding bug in pylint)
        _mock_communicate.return_value = ("file.py:2: [W1401] Invalid char '\xc3'", '')

        # Since we are replacing characters we can't interpet, this should
        # return a valid string with the char replaced with '?'
        quality = PylintQualityReporter('pylint', [])
        violations = quality.violations(u'file.py')
        self.assertEqual(violations, [Violation(2, u"W1401: Invalid char '\ufffd'")])

    def test_non_integer_line_num(self):
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = (dedent(u"""
            file.py:not_a_number: C0111: Missing docstring
            file.py:\u8911: C0111: Missing docstring
        """).encode('utf-8'), '')

        # None of the violations have a valid line number, so they should all be skipped
        violations = PylintQualityReporter('pylint', []).violations(u'file.py')
        self.assertEqual(violations, [])

    def test_quality_error(self):

        # Patch the output of `pylint`
        # to output to stderr
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = ("", 'whoops')

        # Parse the report
        quality = PylintQualityReporter('pylint', [])

        # Expect an error
        self.assertRaises(QualityReporterError, quality.violations, 'file1.py')

    def test_no_quality_issues_newline(self):

        # Patch the output of `pylint`
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = ('\n', '')

        # Parse the report
        quality = PylintQualityReporter('pylint', [])
        self.assertEqual([], quality.violations('file1.py'))

    def test_no_quality_issues_emptystring(self):

        # Patch the output of `pylint`
        _mock_communicate = patch.object(Popen, 'communicate').start()
        _mock_communicate.return_value = ('', '')

        # Parse the report
        quality = PylintQualityReporter('pylint', [])
        self.assertEqual([], quality.violations('file1.py'))

    def test_quality_pregenerated_report(self):

        # When the user provides us with a pre-generated pylint report
        # then use that instead of calling pylint directly.
        pylint_reports = [
            StringIO(dedent(u"""
                path/to/file.py:1: [C0111] Missing docstring
                path/to/file.py:57: [W0511] TODO the name of this method is a little bit confusing
                another/file.py:41: [W1201, assign_default_role] Specify string format arguments as logging function parameters
                another/file.py:175: [C0322, Foo.bar] Operator not preceded by a space
                        x=2+3
                          ^
                        Unicode: \u9404 \u1239
                another/file.py:259: [C0103, bar] Invalid name "\u4920" for type variable (should match [a-z_][a-z0-9_]{2,30}$)
            """.encode('utf-8')).strip()),

            StringIO(dedent(u"""
            path/to/file.py:183: [C0103, Foo.bar.gettag] Invalid name "\u3240" for type argument (should match [a-z_][a-z0-9_]{2,30}$)
            another/file.py:183: [C0111, Foo.bar.gettag] Missing docstring
            """.encode('utf-8')).strip())
        ]

        # Generate the violation report
        quality = PylintQualityReporter('pylint', pylint_reports)

        # Expect that we get the right violations
        expected_violations = [
            Violation(1, u'C0111: Missing docstring'),
            Violation(57, u'W0511: TODO the name of this method is a little bit confusing'),
            Violation(183, u'C0103: Foo.bar.gettag: Invalid name "\u3240" for type argument (should match [a-z_][a-z0-9_]{2,30}$)')
        ]

        # We're not guaranteed that the violations are returned
        # in any particular order.
        actual_violations = quality.violations('path/to/file.py')
        self.assertEqual(len(actual_violations), len(expected_violations))
        for expected in expected_violations:
            self.assertIn(expected, actual_violations)

    def test_quality_pregenerated_report_continuation_char(self):

        # The report contains a non-ASCII continuation char
        pylint_reports = [StringIO("file.py:2: [W1401] Invalid char '\xc3'")]

        # Generate the violation report
        quality = PylintQualityReporter('pylint', pylint_reports)
        violations = quality.violations('file.py')

        # Expect that the char is replaced
        self.assertEqual(violations, [Violation(2, u"W1401: Invalid char '\ufffd'")])
