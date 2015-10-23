#!/usr/bin/env python3
#
# Reverse : Generate an indented asm code (pseudo-C) with colored syntax.
# Copyright (C) 2015    Joel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import shlex
import json

from lib import load_file, init_entry_addr, disasm
from lib.colors import color
from lib.output import print_no_end
from lib.utils import error
from lib.readline import ReadLine
from lib.fileformat.binary import T_BIN_ELF, T_BIN_PE, T_BIN_RAW


class Command():
    def __init__(self, max_args, callback_exec, callback_complete, desc):
        self.max_args = max_args
        self.callback_complete = callback_complete
        self.callback_exec = callback_exec
        self.desc = desc


class Interactive():
    COMMANDS = None
    TAB = "      "
    MAX_PRINT_COMPLETE = 80

    def __init__(self, ctx):
        self.ctx = ctx
        ctx.vim = False

        self.COMMANDS_ALPHA = [
            "calls",
            "da",
            "db",
            "dd",
            "dw",
            "dq",
            "dump",
            "exit",
            "help",
            "info",
            "load",
            "lrawarm",
            "lrawmips",
            "lrawmips64",
            "lrawx86",
            "lrawx64",
            "save",
            "sections",
            "sym",
            "x",
            "display.print_section",
            "display.print_comments",
        ]

        self.COMMANDS = {
            "help": Command(
                0,
                self.__exec_help,
                None,
                [
                "",
                "Display this help"
                ]
            ),

            "save": Command(
                0,
                self.__exec_save,
                None,
                [
                "",
                "Save the database (only symbols and history currently).",
                ]
            ),

            "load": Command(
                1,
                self.__exec_load,
                self.__complete_load,
                [
                "filename",
                "Load a new binary file.",
                ]
            ),

            "lrawx86": Command(
                1,
                self.__exec_lrawx86,
                self.__complete_load,
                [
                "filename",
                "Load a x86 raw file.",
                ]
            ),

            "lrawx64": Command(
                1,
                self.__exec_lrawx64,
                self.__complete_load,
                [
                "filename",
                "Load a x64 raw file.",
                ]
            ),

            "lrawarm": Command(
                1,
                self.__exec_lrawarm,
                self.__complete_load,
                [
                "filename",
                "Load a ARM raw file.",
                ]
            ),

            "lrawmips": Command(
                1,
                self.__exec_lrawmips,
                self.__complete_load,
                [
                "filename",
                "Load a MIPS raw file.",
                ]
            ),

            "lrawmips64": Command(
                1,
                self.__exec_lrawmips64,
                self.__complete_load,
                [
                "filename",
                "Load a MIPS64 raw file.",
                ]
            ),

            "x": Command(
                1,
                self.__exec_x,
                self.__complete_x,
                [
                "[SYMBOL|0xXXXX|EP]",
                "Decompile. By default it will be main.",
                ]
            ),

            "da": Command(
                2,
                self.__exec_data,
                self.__complete_x,
                [
                "SYMBOL|0xXXXX|EP [NB_LINES]",
                "Print data in ascii, it stops when the end of the section is found",
                ]
            ),

            "db": Command(
                2,
                self.__exec_data,
                self.__complete_x,
                [
                "SYMBOL|0xXXXX|EP [NB_LINES]",
                "Print data in bytes, it stops when the end of the section is found",
                ]
            ),

            "dd": Command(
                2,
                self.__exec_data,
                self.__complete_x,
                [
                "SYMBOL|0xXXXX|EP [NB_LINES]",
                "Print data in dwords, it stops when the end of the section is found",
                ]
            ),

            "dw": Command(
                2,
                self.__exec_data,
                self.__complete_x,
                [
                "SYMBOL|0xXXXX|EP [NB_LINES]",
                "Print data in words, it stops when the end of the section is found",
                ]
            ),

            "dq": Command(
                2,
                self.__exec_data,
                self.__complete_x,
                [
                "SYMBOL|0xXXXX|EP [NB_LINES]",
                "Print data in qwords, it stops when the end of the section is found",
                ]
            ),

            # by default it will be ctx.lines
            "dump": Command(
                2,
                self.__exec_dump,
                self.__complete_x,
                [
                "SYMBOL|0xXXXX|EP [NB_LINES]",
                "Disassemble only.",
                ]
            ),

            "set": Command(
                3,
                None,
                None,
                [
                "",
                "Set options"
                ]
            ),

            "sym": Command(
                3,
                self.__exec_sym,
                self.__complete_x,
                [
                "[SYMBOL 0xXXXX] [| FILTER]",
                "Print all symbols or set a new symbol.",
                "You can filter symbols by searching the word FILTER."
                ]
            ),

            "calls": Command(
                1,
                self.__exec_calls,
                self.__complete_x,
                [
                "[SECTION_NAME]",
                "Print all calls which are in the given section"
                ]
            ),

            "exit": Command(
                0,
                self.__exec_exit,
                None,
                [
                "",
                "Exit"
                ]
            ),

            "sections": Command(
                0,
                self.__exec_sections,
                None,
                [
                "",
                "Print all sections",
                ]
            ),

            "info": Command(
                0,
                self.__exec_info,
                None,
                [
                "",
                "Information about the current binary"
                ]
            ),

            "display.print_section": Command(
                0,
                self.__exec_display_print_section,
                None,
                [
                "",
                "Print or not section when an address is found"
                ]
            ),

            "display.print_comments": Command(
                0,
                self.__exec_display_print_comments,
                None,
                [
                "",
                "Print or not comments"
                ]
            ),
        }

        self.database_modified = False

        rl = ReadLine(self.exec_command, self.complete, self.send_control_c)
        self.rl = rl

        if ctx.filename is not None:
            self.__exec_load(["", ctx.filename])

        if ctx.entry is not None:
            self.__exec_x(["", ctx.entry])

        while 1:
            rl.loop()
            if not self.database_modified:
                break
            print("the database was modified, run save or exit to force")


    def send_control_c(self):
        return


    #
    # Returns tuple :
    # - list of completed string (i.e. rest of the current token)
    # - string: the beginning of the current token
    # - if len(list) > 1: it contains the common string between
    #        all possibilities
    #
    # Each sub-complete functions returns only the list.
    #
    def complete(self, line):
        # If last_word == "_" it means that there was spaces before
        # and we want to complete a new arg
        tmp_line = line + "_"
        tokens = shlex.split(tmp_line)
        last_tok = tokens[-1][:-1] # remove the _
        tmp_line = tmp_line[:-1]

        comp = []

        # Complete a command name
        if len(tokens) == 1:
            i = 0
            for cmd in self.COMMANDS_ALPHA:
                if cmd.startswith(last_tok):
                    # To keep spaces
                    comp.append(cmd[len(last_tok):] + " ")
                    i += 1
                    if i == self.MAX_PRINT_COMPLETE:
                        comp = None
                        break
        else:
            try:
                first_tok = tokens[0]
                f = self.COMMANDS[first_tok].callback_complete
                if f is not None:
                    comp = f(tmp_line, len(tokens)-1, last_tok)
            except KeyError:
                pass

        if comp is None:
            print("\ntoo much possibilities")
            return None, None, None

        if len(comp) <= 1:
            return comp, last_tok, None

        common = []
        words_idx = {len(word):i for i, word in enumerate(comp)}
        min_len = min(words_idx)
        ref = words_idx[min_len]

        # Recreate because we have maybe removed words with same length
        words_idx = set(range(len(comp)))
        words_idx.remove(ref)

        for i, char in enumerate(comp[ref]):
            found = True
            for j in words_idx:
                if comp[j][i] != char:
                    found = False
                    break
            if not found:
                break
            common.append(char)

        return comp, last_tok, "".join(common)


    def __complete_load(self, tmp_line, nth_arg, last_tok):
        if nth_arg != 1:
            return []

        comp = []
        basename = os.path.basename(last_tok)
        dirname = os.path.dirname(last_tok)

        if not dirname:
            dirname = "."

        try:
            i = 0
            for f in os.listdir(dirname):
                if f.startswith(basename):
                    f_backslahed = f.replace(" ", "\\ ")
                    if os.path.isdir(os.path.join(dirname, f)):
                        s = f_backslahed + "/"
                    else:
                        s = f_backslahed + " "
                    comp.append(s[len(basename):])
                    i += 1
                    if i == self.MAX_PRINT_COMPLETE:
                        return None
            return comp
        except FileNotFoundError:
            return []


    def __complete_x(self, tmp_line, nth_arg, last_tok):
        if nth_arg != 1 or self.ctx.dis is None:
            return []
        return self.__find_symbol(tmp_line, nth_arg, last_tok)


    def __find_symbol(self, tmp_line, nth_arg, last_tok):
        comp = []
        i = 0
        for sym in self.ctx.dis.binary.symbols:
            if sym.startswith(last_tok):
                comp.append((sym + " ")[len(last_tok):])
                i += 1
                if i == self.MAX_PRINT_COMPLETE:
                    return None
        return comp


    def exec_command(self, line):
        args = shlex.split(line)
        if args[0] not in self.COMMANDS:
            error("unknown command")
            return
        c = self.COMMANDS[args[0]]

        if len(args)-1 > c.max_args:
            error("%s takes max %d args" % (args[0], c.max_args))
            return

        if c.callback_exec is not None:
            c.callback_exec(args)


    def __exec_exit(self, args):
        sys.exit(0)


    def __exec_dump(self, args):
        if self.ctx.dis is None:
            error("load a file before")
            return
        lines = self.ctx.lines
        if len(args) == 1:
            self.ctx.entry = None
        else:
            if len(args) == 3:
                lines = int(args[2])
            self.ctx.entry = args[1]
        if init_entry_addr(self.ctx):
            self.ctx.dis.dump_asm(self.ctx, lines)
            self.ctx.entry = None
            self.ctx.entry_addr = 0


    def __exec_data(self, args):
        if self.ctx.dis is None:
            error("load a file before")
            return
        lines = self.ctx.lines
        if len(args) == 1:
            self.ctx.entry = None
        else:
            if len(args) == 3:
                lines = int(args[2])
            self.ctx.entry = args[1]
        self.ctx.print_data = True
        if init_entry_addr(self.ctx):
            if args[0] == "da":
                self.ctx.dis.dump_data_ascii(self.ctx, lines)
            elif args[0] == "db":
                self.ctx.dis.dump_data(self.ctx, lines, 1)
            elif args[0] == "dw":
                self.ctx.dis.dump_data(self.ctx, lines, 2)
            elif args[0] == "dd":
                self.ctx.dis.dump_data(self.ctx, lines, 4)
            elif args[0] == "dq":
                self.ctx.dis.dump_data(self.ctx, lines, 8)
            self.ctx.entry = None
            self.ctx.entry_addr = 0
            self.ctx.print_data = False


    def __exec_load(self, args):
        if len(args) != 2:
            error("filename required")
            return
        self.ctx.reset_all()
        self.ctx.filename = args[1]
        load_file(self.ctx)
        if self.ctx.db is not None:
            self.rl.history = self.ctx.db["history"]


    def __exec_lrawx86(self, args):
        if len(args) != 2:
            error("filename required")
            return
        self.ctx.reset_all()
        self.ctx.raw_type = "x86"
        self.ctx.raw_big_endian = False
        self.ctx.filename = args[1]
        load_file(self.ctx)


    def __exec_lrawx64(self, args):
        if len(args) != 2:
            error("filename required")
            return
        self.ctx.reset_all()
        self.ctx.raw_type = "x64"
        self.ctx.raw_big_endian = False
        self.ctx.filename = args[1]
        load_file(self.ctx)


    def __exec_lrawarm(self, args):
        if len(args) != 2:
            error("filename required")
            return
        self.ctx.reset_all()
        self.ctx.raw_type = "arm"
        self.ctx.filename = args[1]
        load_file(self.ctx)


    def __exec_lrawmips(self, args):
        if len(args) != 2:
            error("filename required")
            return
        self.ctx.reset_all()
        self.ctx.raw_type = "mips"
        self.ctx.filename = args[1]
        load_file(self.ctx)


    def __exec_lrawmips64(self, args):
        if len(args) != 2:
            error("filename required")
            return
        self.ctx.reset_all()
        self.ctx.raw_type = "mips64"
        self.ctx.filename = args[1]
        load_file(self.ctx)


    def __exec_calls(self, args):
        if len(args) != 2:
            error("section required")
            return
        if self.ctx.dis is None:
            error("load a file before")
            return
        self.ctx.calls_in_section = args[1]
        if init_entry_addr(self.ctx):
            self.ctx.dis.print_calls(self.ctx)
            self.ctx.entry = None
            self.ctx.entry_addr = 0
        self.ctx.calls_in_section = None


    def __exec_sym(self, args):
        if self.ctx.dis is None:
            error("load a file before")
            return

        if len(args) == 1:
            self.ctx.dis.print_symbols(self.ctx.sectionsname)
            return

        if args[1][0] == "|":
            if len(args) == 2 or len(args) > 3:
                error("bad arguments (warn: need spaces between |)")
                return
            self.ctx.dis.print_symbols(self.ctx.sectionsname, args[2])
            return

        if len(args) > 3:
            error("bad arguments")
            return

        if len(args) == 2:
            error("an address is required to save the symbol")
            return

        if not args[2].startswith("0x"):
            error("the address should starts with 0x")
            return

        # Save new symbol
        try:
            addr = int(args[2], 16)
            self.database_modified = True

            if args[1] in self.ctx.dis.binary.symbols:
                last = self.ctx.dis.binary.symbols[args[1]]
                del self.ctx.dis.binary.reverse_symbols[last]

            self.ctx.dis.binary.symbols[args[1]] = addr
            self.ctx.dis.binary.reverse_symbols[addr] = args[1]

        except:
            error("there was an error when creating a symbol")


    def __exec_x(self, args):
        if self.ctx.dis is None:
            error("load a file before")
            return
        if len(args) == 1:
            self.ctx.entry = None
        else:
            self.ctx.entry = args[1]
        self.ctx.reset_vars()
        if init_entry_addr(self.ctx):
            disasm(self.ctx)
            self.ctx.entry = None
            self.ctx.entry_addr = 0


    def __exec_help(self, args):
        for name in self.COMMANDS_ALPHA:
            cmd = self.COMMANDS[name]
            if cmd.callback_exec is not None:
                self.rl.print(color(name, 2))
                self.rl.print(" ")
                for i, line in enumerate(cmd.desc):
                    if i > 0:
                        self.rl.print(self.TAB)
                    self.rl.print(line)
                    self.rl.print("\n")


    def __exec_sections(self, args):
        if self.ctx.dis is None:
            error("load a file before")
            return

        self.rl.print("NAME".ljust(20))
        self.rl.print(" [ START - END - SIZE ]\n")

        for (name, start, end) in self.ctx.dis.binary.iter_sections():
            self.ctx.dis.print_section_meta(name, start, end)


    def __exec_info(self, args):
        if self.ctx.filename is None:
            print("no file loaded")
            return
        print("File:", self.ctx.filename)

        statinfo = os.stat(self.ctx.filename)
        print("Size: %.2f ko" % (statinfo.st_size/1024.))

        print_no_end("Type: ")

        ty = self.ctx.dis.binary.type
        if ty == T_BIN_PE:
            print("PE")
        elif ty == T_BIN_ELF:
            print("ELF")
        elif ty == T_BIN_RAW:
            print("RAW")

        import capstone as CAPSTONE

        arch, mode = self.ctx.dis.binary.get_arch()

        print_no_end("Arch: ")

        if arch == CAPSTONE.CS_ARCH_X86:
            if mode & CAPSTONE.CS_MODE_32:
                print("x86")
            elif mode & CAPSTONE.CS_MODE_64:
                print("x64")
        elif arch == CAPSTONE.CS_ARCH_ARM:
            print("arm")
        elif arch == CAPSTONE.CS_ARCH_MIPS:
            if mode & CAPSTONE.CS_MODE_32:
                print("mips")
            elif mode & CAPSTONE.CS_MODE_64:
                print("mips64 (octeon)")
        else:
            print("not supported")

        if mode & CAPSTONE.CS_MODE_BIG_ENDIAN:
            print("Endianess: big endian")
        else:
            print("Endianess: little endian")


    def __exec_display_print_section(self, args):
        if self.ctx.sectionsname:
            print("now it's off")
            self.ctx.sectionsname = False
        else:
            print("now it's on")
            self.ctx.sectionsname = True


    def __exec_display_print_comments(self, args):
        if self.ctx.comments:
            print("now it's off")
            self.ctx.comments = False
        else:
            print("now it's on")
            self.ctx.comments = True


    def __exec_save(self, args):
        fd = open(self.ctx.db_path, "w+")
        db = {
            "symbols": self.ctx.dis.binary.symbols,
            "history": self.rl.history,
        }
        fd.write(json.dumps(db))
        fd.close()
        print("database saved to", self.ctx.db_path)
        self.database_modified = False
