#!/usr/bin/env python
# -*- coding: utf-8 -*-

import lldb
import re
import optparse
import ds 
import shlex
import pdb

class GlobalOptions(object):
    symbols = {} # value = {breakpoint_id: ((regex, module), options)}

    @staticmethod
    def addSymbols(regex_module, options, breakpoint):
        key = str(breakpoint.GetID())
        GlobalOptions.symbols[key] = (regex_module, options)
        

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(
        'command script add -f breakifonfuncset.breakifonfuncset biofset')

def breakifonfuncset(debugger, command, exe_ctx, result, internal_dict):
    '''
    usage: biof regex0 [Optional_ModuleName] ||| regex1  ModuleName1 ||| regex2 ModuleName2
    Regex breakpoint that stops only if the second regex breakpoint is in the stack trace
    For example, to only stop if code in the "Test" module resulted the setTintColor: being called
    biof setTintColor: ||| . Test 
    '''
    command_args = shlex.split(command, posix=False)
    parser = generateOptionParser()
    try:
        (options, args) = parser.parse_args(command_args)
    except:
        result.SetError("Error parsing")
        return 

    target = exe_ctx.target
    if len(command.split('|||')) < 2:
        result.SetError(parser.usage)
        return

    t = " ".join(args).split('|||')
    clean_command = t[0].strip().split()
    if len(clean_command) == 2:
        breakpoint = target.BreakpointCreateByRegex(clean_command[0], clean_command[1])
    else:
        breakpoint = target.BreakpointCreateByRegex(clean_command[0], None)

    # 后续 regex_module 的存储
    subCount = len(t)
    regex_modules = []
    for idx in range(1, len(t)):
        subcmd = t[idx].strip().split()
        moduleName = subcmd[1]
        module = target.module[moduleName]
        if not module:
            result.SetError('Invalid module {}'.format(moduleName))
            return
        searchQuery = subcmd[0]
        regex_modules.append((searchQuery, moduleName))
    GlobalOptions.addSymbols(regex_modules, options, breakpoint)

    # 设置回掉函数
    breakpoint.SetScriptCallbackFunction("breakifonfuncset.breakpointHandler")

    if not breakpoint.IsValid() or breakpoint.num_locations == 0:
        result.AppendWarning("Breakpoint isn't valid or hasn't found any hits: " + clean_command[0])
    else:
        # result.AppendMessage("\"{}\" produced {} hits\nOnly will stop if the following stack frame symbols contain:\n{}` \"{}\" produced {} hits".format( 
        #      clean_command[0], breakpoint.num_locations, module.file.basename, searchQuery, len(s)) )
        result.AppendMessage("\"{}\" produced {} hits\nOnly will stop if the following stack frame symbols contain:\n{}` \"{}\" produced hits".format( 
             clean_command[0], breakpoint.num_locations, module.file.basename, searchQuery) )


def breakpointHandler(frame, bp_loc, dict):
    if len(GlobalOptions.symbols) == 0:
        print("womp something internal called reload LLDB init which removed the global symbols")
        return True
    key = str(bp_loc.GetBreakpoint().GetID())
    regex_modules = GlobalOptions.symbols[key][0]
    options = GlobalOptions.symbols[key][1]

    function_name = frame.GetFunctionName()
    thread = frame.thread

    if len(regex_modules) >= len(thread.frames):
        print('breakifonfuncset ** try hit, regex_modules >= thread.frames')
        return False

    if not options.direct or options.direct == 'd':
        for idx in range(len(regex_modules)):
            cframe = thread.frames[idx + 1]
            if cframe.module.file.basename != regex_modules[idx][1]:
                print("breakifonfuncset ** {} module != {}".formart(str(cframe), regex_modules[idx][1]))
                return False
            if not re.search(regex_modules[idx][0], cframe.symbol.name):
                print("breakifonfuncset ** regex: {} can`t re {}".format(regex_modules[idx][0], cframe.symbol.name))
                return False
        print("breakifonfuncset ** all re cmp")
        return True
    elif options.direct == 's':
        rescmpIdx = 0
        res = []
        for cframe in thread.frames:
            if rescmpIdx >= len(regex_modules):
                break

            if cframe.module.file.basename != regex_modules[rescmpIdx][1]:
                continue

            m = re.search(regex_modules[rescmpIdx][0], cframe.symbol.name)
            if m:
                res.append(m)
                rescmpIdx += 1

        isHit = len(res) == len(regex_modules)
        if not isHit:
            print("breakifonfuncset ** try hit -s, regex is {} times , total is {} \n".format(len(res), len(regex_modules)))
        else:
            print("breakifonfuncset ** hit -s regex {} times".format(len(res)))
        return isHit
    elif options.direct == 'm':
        temThreadFrames = [frame for frame in thread.frames]
        res = []
        for regexmodule in regex_modules:

            for cframe in thread.frames:
                if cframe.module.file.basename != regexmodule[1]:
                    continue

                m = re.search(regexmodule[0], cframe.symbol.name)
                if m and cframe in temThreadFrames:
                    res.append(m)
                    temThreadFrames.remove(cframe)
                    break

        isHit = len(res) == len(regex_modules)
        if not isHit:
            print("breakifonfuncset ** try hit -m, regex is {} times , total is {}".format(len(res), len(regex_modules)))
        else:
            print("breakifonfuncset ** hit -m regex {} times".format(len(res)))
        return isHit
    else:
        print("breakifonfuncset ** not define optinos.direct = {}".format(options.direct))
        return False


def generateOptionParser():
    usage = breakifonfuncset.__doc__
    parser = optparse.OptionParser(usage=usage, prog="biof")
    parser.add_option("-d", "--direct",
                  action="store",
                  default='d', # d: direct; s: sort; m:mesrsy
                  dest="direct",
                  help="Only stop if the regexs the breakpoint;\n d:direct\n s: sort\n m:mesrsy")
    return parser
