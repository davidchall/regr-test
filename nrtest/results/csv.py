# Avoid confusion with CPython csv module
from __future__ import absolute_import

from six.moves import range
from csv import reader, Sniffer, Error as CsvError
import logging

from nrtest.results import Result


class NumericCsvResult(Result):
    """Numeric results stored in a comma separated value file format.
    """
    def __init__(self, fpath):
        super(NumericCsvResult, self).__init__()
        self.fpath = fpath
        self._identify_format()

    def _identify_format(self):
        """Guess the csv formatting dialect and count the number of lines
        occupied by the header. The header is recognised as lines that begin
        with the # character, or a single line of non-float values.
        """
        self.n_header_lines = 0
        with open(self.fpath) as csvfile:

            # check for initial rows that begin with hash
            pos = csvfile.tell()
            line = csvfile.readline()
            while line:
                if line.startswith('#'):
                    self.n_header_lines += 1
                    pos = csvfile.tell()
                    line = csvfile.readline()
                else:
                    break

            # is the first line without a hash in fact a header line?
            csvfile.seek(pos)
            sample = csvfile.read(1024)
            # sniffer confused if there is only one cell
            if len(sample.split()) <= 1:
                self.dialect = 'excel'
            # otherwise use standard python csv sniffer
            else:
                try:
                    self.dialect = Sniffer().sniff(sample, ',:;\t ')
                    if Sniffer().has_header(sample):
                        self.n_header_lines += 1
                except CsvError:
                    self.dialect = 'excel'

    def compare(self, ref):
        """Compare to a reference result.

        This method skips past the headers and starts comparing rows of data.
        It returns delta=999 if:
            - number of rows is different
            - number of columns on any row is different
            - error reading either CSV file
            - string compared to float
            - different strings in the same cell

        Returns:
            max_delta: maximum relative difference between results
            avg_delta: mean relative difference between results
        """
        max_delta, avg_delta = 0.0, 0.0
        FAILURE = (999.9, 999.9)

        # Requires >=2.7 or >=3.1
        with open(self.fpath, 'rb') as f, open(ref.fpath, 'rb') as f_ref:
            for _ in range(self.n_header_lines):
                next(f)
            for _ in range(ref.n_header_lines):
                next(f_ref)

            rdr = reader(f, dialect=self.dialect)
            rdr_ref = reader(f_ref, dialect=ref.dialect)

            n_cells = 0
            n_eofs = 0
            while n_eofs == 0:
                try:
                    row = next(rdr)
                except CsvError as e:
                    msg = 'Problem reading line %d of "%s"'
                    logging.error(msg % (rdr.line_num, self.fpath))
                    logging.error(e)
                    return FAILURE
                except StopIteration:
                    n_eofs += 1

                try:
                    row_ref = next(rdr_ref)
                except CsvError as e:
                    msg = 'Problem reading line %d of "%s"'
                    logging.error(msg % (rdr_ref.line_num, ref.fpath))
                    logging.error(e)
                    return FAILURE
                except StopIteration:
                    n_eofs += 1

                if n_eofs == 2:
                    break
                elif n_eofs == 1:
                    msg = 'Results have different # rows: "%s" and "%s"'
                    logging.debug(msg % (self.fpath, ref.fpath))
                    return FAILURE
                if len(row) != len(row_ref):
                    msg = 'Results have different # columns: "%s" and "%s"'
                    logging.debug(msg % (self.fpath, ref.fpath))
                    return FAILURE

                for i in range(len(row)):
                    try:
                        cell = float(row[i])
                    except ValueError:
                        cell = str(row[i])
                    try:
                        cell_ref = float(row_ref[i])
                    except ValueError:
                        cell_ref = str(row_ref[i])

                    if isinstance(cell, float) and isinstance(cell_ref, float):
                        if cell == 0 and cell_ref == 0:
                            delta = 0.0
                        elif cell_ref == 0:
                            delta = 999.9
                        else:
                            delta = abs((cell - cell_ref) / cell_ref)

                        max_delta = max(delta, max_delta)
                        avg_delta += delta
                        n_cells += 1
                    elif isinstance(cell, str) and isinstance(cell_ref, str):
                        if cell.strip() != cell_ref.strip():
                            msg = 'String mismatch found on line %i of "%s"'
                            logging.debug(msg % (i+1, self.fpath))
                            return FAILURE
                    else:
                        msg = 'Incompatible value types on line %i of "%s"'
                        logging.debug(msg % (i+1, self.fpath))
                        return FAILURE

        if n_cells > 0:
            avg_delta /= n_cells
        return max_delta, avg_delta
