import os
import re
import socket
import time
from typing import Any, List, Optional, Union

from robot.api import logger
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.utils import Matcher

from .py3270 import Emulator


class x3270(object):
    def __init__(
        self,
        visible: bool,
        timeout: int,
        wait_time: float,
        wait_time_after_write: float,
        img_folder: str,
    ) -> None:
        self.visible = visible
        self.timeout = timeout
        self.wait = wait_time
        self.wait_write = wait_time_after_write
        self.imgfolder = img_folder
        self.mf: Emulator = None  # type: ignore
        # Try Catch to run in Pycharm, and make a documentation in libdoc with no error
        try:
            self.output_folder = BuiltIn().get_variable_value("${OUTPUT DIR}")
        except RobotNotRunningError:
            self.output_folder = os.getcwd()

    @keyword("Change Timeout")
    def change_timeout(self, seconds: int) -> None:
        """
        Change the timeout for connection in seconds.

        Example:
            | Change Timeout | 3 |
        """
        self.timeout = seconds

    @keyword("Open Connection")
    def open_connection(
        self,
        host: str,
        LU: Optional[str] = None,
        port: int = 23,
        extra_args: Optional[Union[List[str], os.PathLike]] = None,
    ):
        """Create a connection to IBM3270 mainframe with the default port 23. To make a connection with the mainframe
        you only must inform the Host. You can pass the Logical Unit Name and the Port as optional.

        If you wish, you can provide further configuration data to ``extra_args``. ``extra_args`` takes in a list,
        or a path to a file, containing [https://x3270.miraheze.org/wiki/Category:Command-line_options|x3270 command line options].
        Entries in the argfile can be on one line or multiple lines. Lines starting with "#" are considered comments.
        | # example_argfile_oneline.txt
        | --accepthostname myhost.com

        | # example_argfile_multiline.txt
        | --accepthostname myhost.com
        | # this is a comment
        | --charset french

        Please make sure the arguments you are providing are available for your specific x3270 application and version.

        Example:
            | Open Connection | Hostname |
            | Open Connection | Hostname | LU=LUname |
            | Open Connection | Hostname | port=992 |
            | ${extra_args}   | Create List | --accepthostname | myhost.com | --cafile | ${CURDIR}/cafile.crt |
            | Open Connection | Hostname | extra_args=${extra_args} |
            | Open Connection | Hostname | extra_args=${CURDIR}/argfile.txt |
        """
        self.host = host
        self.lu = LU
        self.port = port
        if self.lu:
            self.credential = "%s@%s:%s" % (self.lu, self.host, self.port)
        else:
            self.credential = "%s:%s" % (self.host, self.port)
        if self.mf:
            self.close_connection()
        self.mf = Emulator(self.visible, self.timeout, extra_args)
        self.mf.connect(self.credential)

    @keyword("Close Connection")
    def close_connection(self) -> None:
        """Disconnect from the host."""
        try:
            self.mf.terminate()
        except socket.error:
            pass
        self.mf = None  # type: ignore

    @keyword("Change Wait Time")
    def change_wait_time(self, wait_time: float) -> None:
        """To give time for the mainframe screen to be "drawn" and receive the next commands, a "wait time" has been
        created, which by default is set to 0.5 seconds. This is a sleep applied AFTER the following keywords:

        - `Execute Command`
        - `Send Enter`
        - `Send PF`
        - `Write`
        - `Write in position`

        If you want to change this value, just use this keyword passing the time in seconds.

        Example:
            | Change Wait Time | 0.1 |
            | Change Wait Time | 2 |
        """
        self.wait = wait_time

    @keyword("Change Wait Time After Write")
    def change_wait_time_after_write(self, wait_time_after_write: float) -> None:
        """To give the user time to see what is happening inside the mainframe, a "wait time after write" has
        been created, which by default is set to 0 seconds. This is a sleep applied AFTER sending a string in these
        keywords:

        - `Write`
        - `Write Bare`
        - `Write in position`
        - `Write Bare in position`

        If you want to change this value, just use this keyword passing the time in seconds.

        Note: This keyword is useful for debug purpose

        Example:
            | Change Wait Time After Write | 0.5 |
            | Change Wait Time After Write | 2 |
        """
        self.wait_write = wait_time_after_write

    @keyword("Read")
    def read(self, ypos: int, xpos: int, length: int) -> str:
        """Get a string of ``length`` at screen co-ordinates ``ypos`` / ``xpos``.

        Co-ordinates are 1 based, as listed in the status area of the terminal.

        Example for read a string in the position y=8 / x=10 of a length 15:
            | ${value} | Read | 8 | 10 | 15 |
        """
        self._check_limits(ypos, xpos)
        # Checks if the user has passed a length that will be larger than the x limit of the screen.
        if (xpos + length) > (80 + 1):
            raise Exception(
                "You have exceeded the x-axis limit of the mainframe screen"
            )
        string = self.mf.string_get(ypos, xpos, length)
        return string

    @keyword("Read All Screen")
    def read_all_screen(self) -> str:
        """Read the current screen and returns all content in one string.

        This is useful if your automation scripts should take different routes depending
        on a message shown on the screen.

        Example:
            | ${screen} | Read All Screen              |
            | IF   | 'certain text' in '''${screen}''' |
            |      | Do Something                      |
            | ELSE |                                   |
            |      | Do Something Else                 |
            | END  |                                   |
        """
        return self._read_all_screen()

    @keyword("Execute Command")
    def execute_command(self, cmd: str) -> None:
        """Execute a [http://x3270.bgp.nu/wc3270-man.html#Actions|x3270 command].

        Example:
            | Execute Command | Enter |
            | Execute Command | Home |
            | Execute Command | Tab |
            | Execute Command | PF(1) |
        """
        self.mf.exec_command(cmd.encode("utf-8"))
        time.sleep(self.wait)

    @keyword("Set Screenshot Folder")
    def set_screenshot_folder(self, path: str) -> None:
        r"""Set a folder to keep the html files generated by the `Take Screenshot` keyword.

        Note that the folder needs to exist before running your automation scripts. Else the images
        will be stored in the ``${OUTPUT DIR}`` set by robotframework.

        Example:
            | Set Screenshot Folder | C:\\Temp\\Images |
        """
        if os.path.exists(os.path.normpath(os.path.join(self.output_folder, path))):
            self.imgfolder = path
        else:
            logger.error('Given screenshots path "%s" does not exist' % path)
            logger.warn('Screenshots will be saved in "%s"' % self.imgfolder)

    @keyword("Take Screenshot")
    def take_screenshot(self, height: int = 410, width: int = 670) -> None:
        """Generate a screenshot of the IBM 3270 Mainframe in a html format. The
        default folder is the log folder of RobotFramework, if you want change see the `Set Screenshot Folder`.

        The Screenshot is printed in a iframe log, with the values of height=410 and width=670, you
        can change this values passing them to the keyword.

        Example:
            | Take Screenshot |
            | Take Screenshot | height=500 | width=700 |
        """
        filename_prefix = "screenshot"
        extension = "html"
        filename_sufix = round(time.time() * 1000)
        filepath = os.path.join(
            self.imgfolder, "%s_%s.%s" % (filename_prefix, filename_sufix, extension)
        )
        self.mf.save_screen(os.path.join(self.output_folder, filepath))
        logger.write(
            '<iframe src="%s" height="%s" width="%s"></iframe>'
            % (filepath.replace("\\", "/"), height, width),
            level="INFO",
            html=True,
        )

    @keyword("Wait Field Detected")
    def wait_field_detected(self) -> None:
        """Wait until the screen is ready, the cursor has been positioned
        on a modifiable field, and the keyboard is unlocked.

        Sometimes the server will "unlock" the keyboard but the screen
        will not yet be ready.  In that case, an attempt to read or write to the
        screen will result in a 'E' keyboard status because we tried to read from
        a screen that is not ready yet.

        Using this method tells the client to wait until a field is
        detected and the cursor has been positioned on it.
        """
        self.mf.wait_for_field()

    @keyword("Delete Char")
    def delete_char(
        self, ypos: Optional[int] = None, xpos: Optional[int] = None
    ) -> None:
        """Delete the character under the cursor. If you want to delete a character that is in
        another position, simply pass the coordinates ``ypos`` / ``xpos``.

        Co-ordinates are 1 based, as listed in the status area of the
        terminal.

        Example:
            | Delete Char |
            | Delete Char | ypos=9 | xpos=25 |
        """
        if ypos is not None and xpos is not None:
            self.mf.move_to(ypos, xpos)
        self.mf.exec_command(b"Delete")

    @keyword("Delete Field")
    def delete_field(
        self, ypos: Optional[int] = None, xpos: Optional[int] = None
    ) -> None:
        """Delete the entire content of a field at the current cursor location and positions
        the cursor at beginning of field. If you want to delete a field that is in
        another position, simply pass the coordinates ``ypos`` / ``xpos`` of any part in the field.

        Co-ordinates are 1 based, as listed in the status area of the
        terminal.

        Example:
            | Delete Field |
            | Delete Field | ypos=12 | xpos=6 |
        """
        if ypos is not None and xpos is not None:
            self.mf.move_to(ypos, xpos)
        self.mf.delete_field()

    @keyword("Send Enter")
    def send_enter(self) -> None:
        """Send an Enter to the screen."""
        self.mf.send_enter()
        time.sleep(self.wait)

    @keyword("Move Next Field")
    def move_next_field(self) -> None:
        """Move the cursor to the next input field. Equivalent to pressing the Tab key."""
        self.mf.exec_command(b"Tab")

    @keyword("Move Previous Field")
    def move_previous_field(self) -> None:
        """Move the cursor to the previous input field. Equivalent to pressing the Shift+Tab keys."""
        self.mf.exec_command(b"BackTab")

    @keyword("Send PF")
    def send_PF(self, PF: str) -> None:
        """Send a Program Function to the screen.

        Example:
               | Send PF | 3 |
        """
        self.mf.exec_command(("PF(" + PF + ")").encode("utf-8"))
        time.sleep(self.wait)

    @keyword("Write")
    def write(self, txt: str) -> None:
        """Send a string *and Enter* to the screen at the current cursor location.

        Example:
            | Write | something |
        """
        self._write(txt, enter=1)

    @keyword("Write Bare")
    def write_bare(self, txt: str) -> None:
        """Send only the string to the screen at the current cursor location.

        Example:
            | Write Bare | something |
        """
        self._write(txt)

    @keyword("Write In Position")
    def write_in_position(self, txt: str, ypos: int, xpos: int) -> None:
        """Send a string *and Enter* to the screen at screen co-ordinates ``ypos`` / ``xpos``.

        Co-ordinates are 1 based, as listed in the status area of the
        terminal.

        Example:
            | Write in Position | something | 9 | 11 |
        """
        self._write(txt, ypos, xpos, enter=1)

    @keyword("Write Bare In Position")
    def write_bare_in_position(self, txt: str, ypos: int, xpos: int):
        """Send only the string to the screen at screen co-ordinates ``ypos`` / ``xpos``.

        Co-ordinates are 1 based, as listed in the status area of the
        terminal.

        Example:
            | Write Bare in Position | something | 9 | 11 |
        """
        self._write(txt, ypos, xpos)

    def _write(
        self,
        txt: Any,
        ypos: Optional[int] = None,
        xpos: Optional[int] = None,
        enter: int = 0,
    ) -> None:
        txt = txt.encode("unicode_escape")
        if ypos is not None and xpos is not None:
            self._check_limits(ypos, xpos)
            self.mf.send_string(txt, ypos, xpos)
        else:
            self.mf.send_string(txt)
        time.sleep(self.wait_write)
        for i in range(enter):
            self.mf.send_enter()
            time.sleep(self.wait)

    @keyword("Wait Until String")
    def wait_until_string(self, txt: str, timeout: int = 5) -> str:
        """Wait until a string exists on the mainframe screen to perform the next step. If the string does not appear in
        5 seconds, the keyword will raise an exception. You can define a different timeout.

        Example:
            | Wait Until String | something |
            | Wait Until String | something | timeout=10 |
        """
        max_time = time.ctime(int(time.time()) + timeout)
        while time.ctime(int(time.time())) < max_time:
            result = self._search_string(str(txt))
            if result:
                return txt
        raise Exception(
            'String "' + txt + '" not found in ' + str(timeout) + " seconds"
        )

    def _search_string(self, string: str, ignore_case: bool = False) -> bool:
        """Search if a string exists on the mainframe screen and return True or False."""

        def __read_screen(string: str, ignore_case: bool) -> bool:
            for ypos in range(24):
                line = self.mf.string_get(ypos + 1, 1, 80)
                if ignore_case:
                    line = line.lower()
                if string in line:
                    return True
            return False

        status = __read_screen(string, ignore_case)
        return status

    @keyword("Page Should Contain String")
    def page_should_contain_string(
        self, txt: str, ignore_case: bool = False, error_message: Optional[str] = None
    ) -> None:
        """Assert that a given string exists on the mainframe screen.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Contain String | something |
            | Page Should Contain String | someTHING | ignore_case=True |
            | Page Should Contain String | something | error_message=New error message |
        """
        message = 'The string "' + txt + '" was not found'
        if error_message:
            message = error_message
        if ignore_case:
            txt = txt.lower()
        result = self._search_string(txt, ignore_case)
        if not result:
            raise Exception(message)
        logger.info('The string "' + txt + '" was found')

    @keyword("Page Should Not Contain String")
    def page_should_not_contain_string(
        self, txt: str, ignore_case: bool = False, error_message: Optional[str] = None
    ) -> None:
        """Assert that a given string does NOT exists on the mainframe screen.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Not Contain String | something |
            | Page Should Not Contain String | someTHING | ignore_case=True |
            | Page Should Not Contain String | something | error_message=New error message |
        """
        message = 'The string "' + txt + '" was found'
        if error_message:
            message = error_message
        if ignore_case:
            txt = txt.lower()
        result = self._search_string(txt, ignore_case)
        if result:
            raise Exception(message)

    @keyword("Page Should Contain Any String")
    def page_should_contain_any_string(
        self,
        list_string: List[str],
        ignore_case: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Assert that one of the strings in a given list exists on the mainframe screen.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Contain Any String | ${list_of_string} |
            | Page Should Contain Any String | ${list_of_string} | ignore_case=True |
            | Page Should Contain Any String | ${list_of_string} | error_message=New error message |
        """
        message = 'The strings "' + str(list_string) + '" were not found'
        if error_message:
            message = error_message
        if ignore_case:
            list_string = [item.lower() for item in list_string]
        for string in list_string:
            result = self._search_string(string, ignore_case)
            if result:
                break
        if not result:
            raise Exception(message)

    @keyword("Page Should Not Contain Any String")
    def page_should_not_contain_any_string(
        self,
        list_string: List[str],
        ignore_case: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Assert that none of the strings in a given list exists on the mainframe screen. If one or more of the
        string are found, the keyword will raise a exception.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Not Contain Any Strings | ${list_of_string} |
            | Page Should Not Contain Any Strings | ${list_of_string} | ignore_case=True |
            | Page Should Not Contain Any Strings | ${list_of_string} | error_message=New error message |
        """
        self._compare_all_list_with_screen_text(
            list_string, ignore_case, error_message, should_match=False
        )

    @keyword("Page Should Contain All Strings")
    def page_should_contain_all_strings(
        self,
        list_string: List[str],
        ignore_case: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Assert that all of the strings in a given list exist on the mainframe screen.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Contain All Strings | ${list_of_string} |
            | Page Should Contain All Strings | ${list_of_string} | ignore_case=True |
            | Page Should Contain All Strings | ${list_of_string} | error_message=New error message |
        """
        self._compare_all_list_with_screen_text(
            list_string, ignore_case, error_message, should_match=True
        )

    @keyword("Page Should Not Contain All Strings")
    def page_should_not_contain_all_strings(
        self,
        list_string: List[str],
        ignore_case: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Fails if one of the strings in a given list exists on the mainframe screen. If one of the string
        are found, the keyword will raise a exception.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Not Contain All Strings | ${list_of_string} |
            | Page Should Not Contain All Strings | ${list_of_string} | ignore_case=True |
            | Page Should Not Contain All Strings | ${list_of_string} | error_message=New error message |
        """
        message = error_message
        if ignore_case:
            list_string = [item.lower() for item in list_string]
        for string in list_string:
            result = self._search_string(string, ignore_case)
            if result:
                if message is None:
                    message = 'The string "' + string + '" was found'
                raise Exception(message)

    @keyword("Page Should Contain String X Times")
    def page_should_contain_string_x_times(
        self,
        txt: str,
        number: int,
        ignore_case: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """Asserts that the entered string appears the desired number of times on the mainframe screen.

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
               | Page Should Contain String X Times | something | 3 |
               | Page Should Contain String X Times | someTHING | 3 | ignore_case=True |
               | Page Should Contain String X Times | something | 3 | error_message=New error message |
        """
        message = error_message
        number = number
        all_screen = self._read_all_screen()
        if ignore_case:
            txt = txt.lower()
            all_screen = all_screen.lower()
        number_of_times = all_screen.count(txt)
        if number_of_times != number:
            if message is None:
                message = f'The string "{txt}" was not found "{number}" times, it appears "{number_of_times}" times'
            raise Exception(message)
        logger.info('The string "' + txt + '" was found "' + str(number) + '" times')

    @keyword("Page Should Match Regex")
    def page_should_match_regex(self, regex_pattern: str) -> None:
        r"""Fails if string does not match pattern as a regular expression. Regular expression check is
        implemented using the Python [https://docs.python.org/2/library/re.html|re module]. Python's
        regular expression syntax is derived from Perl, and it is thus also very similar to the syntax used,
        for example, in Java, Ruby and .NET.

        Backslash is an escape character in the test data, and possible backslashes in the pattern must
        thus be escaped with another backslash (e.g. \\d\\w+).
        """
        page_text = self._read_all_screen()
        if not re.findall(regex_pattern, page_text, re.MULTILINE):
            raise Exception('No matches found for "' + regex_pattern + '" pattern')

    @keyword("Page Should Not Match Regex")
    def page_should_not_match_regex(self, regex_pattern: str) -> None:
        r"""Fails if string does match pattern as a regular expression. Regular expression check is
        implemented using the Python [https://docs.python.org/2/library/re.html|re module]. Python's
        regular expression syntax is derived from Perl, and it is thus also very similar to the syntax used,
        for example, in Java, Ruby and .NET.

        Backslash is an escape character in the test data, and possible backslashes in the pattern must
        thus be escaped with another backslash (e.g. \\d\\w+).
        """
        page_text = self._read_all_screen()
        if re.findall(regex_pattern, page_text, re.MULTILINE):
            raise Exception(
                'There are matches found for "' + regex_pattern + '" pattern'
            )

    @keyword("Page Should Contain Match")
    def page_should_contain_match(
        self, txt: str, ignore_case: bool = False, error_message: Optional[str] = None
    ) -> None:
        """Assert that the text displayed on the mainframe screen matches the given pattern.

        Pattern matching is similar to matching files in a shell, and it is always case sensitive.
        In the pattern, * matches anything and ? matches any single character.

        Note that for this keyword the entire screen is considered a string. So if you want to search
        for the string "something" and it is somewhere other than at the beginning or end of the screen, it
        should be reported as follows: **something**

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Contain Match | **something** |
            | Page Should Contain Match | **so???hing** |
            | Page Should Contain Match | **someTHING** | ignore_case=True |
            | Page Should Contain Match | **something** | error_message=New error message |
        """
        message = error_message
        all_screen = self._read_all_screen()
        if ignore_case:
            txt = txt.lower()
            all_screen = all_screen.lower()
        matcher = Matcher(txt, caseless=False, spaceless=False)
        result = matcher.match(all_screen)
        if not result:
            if message is None:
                message = 'No matches found for "' + txt + '" pattern'
            raise Exception(message)

    @keyword("Page Should Not Contain Match")
    def page_should_not_contain_match(
        self, txt: str, ignore_case: bool = False, error_message: Optional[str] = None
    ) -> None:
        """Assert that the text displayed on the mainframe screen does NOT match the given pattern.

        Pattern matching is similar to matching files in a shell, and it is always case sensitive.
        In the pattern, * matches anything and ? matches any single character.

        Note that for this keyword the entire screen is considered a string. So if you want to search
        for the string "something" and it is somewhere other than at the beginning or end of the screen, it
        should be reported as follows: **something**

        The assertion is case sensitive. If you want it to be case insensitive, you can pass the argument ignore_case=True.

        You can change the exception message by setting a custom string to error_message.

        Example:
            | Page Should Not Contain Match | **something** |
            | Page Should Not Contain Match | **so???hing** |
            | Page Should Not Contain Match | **someTHING** | ignore_case=True |
            | Page Should Not Contain Match | **something** | error_message=New error message |
        """
        message = error_message
        all_screen = self._read_all_screen()
        if ignore_case:
            txt = txt.lower()
            all_screen = all_screen.lower()
        matcher = Matcher(txt, caseless=False, spaceless=False)
        result = matcher.match(all_screen)
        if result:
            if message is None:
                message = 'There are matches found for "' + txt + '" pattern'
            raise Exception(message)

    def _read_all_screen(self) -> str:
        """Read all the mainframe screen and return in a single string."""
        full_text = ""
        for ypos in range(24):
            full_text += self.mf.string_get(ypos + 1, 1, 80)
        return full_text

    def _compare_all_list_with_screen_text(
        self,
        list_string: List[str],
        ignore_case: bool,
        message: Optional[str],
        should_match: bool,
    ) -> None:
        if ignore_case:
            list_string = [item.lower() for item in list_string]
        for string in list_string:
            result = self._search_string(string, ignore_case)
            if not should_match and result:
                if message is None:
                    message = 'The string "' + string + '" was found'
                raise Exception(message)
            elif should_match and not result:
                if message is None:
                    message = 'The string "' + string + '" was not found'
                raise Exception(message)

    @staticmethod
    def _check_limits(ypos: int, xpos: int):
        """Checks if the user has passed some coordinate y / x greater than that existing in the mainframe"""
        if ypos > 24:
            raise Exception(
                "You have exceeded the y-axis limit of the mainframe screen"
            )
        if xpos > 80:
            raise Exception(
                "You have exceeded the x-axis limit of the mainframe screen"
            )
