#from IPython.kernel.zmq.kernelbase import Kernel
from IPython.display import HTML, display
from IPython.display import Image
from pexpect import replwrap, EOF
from metakernel import MetaKernel
from IPython.utils.jsonutil import json_clean, encode_images


from subprocess import check_output
from os import unlink
from difflib import get_close_matches

from pprint import pprint
import json
import base64
import imghdr
import re
import signal
import urllib
import time
import shutil
import os

#Create Logger
import logging
logger= logging.getLogger('')
logger.setLevel(logging.DEBUG)


__version__ = '0.1'

version_pat = re.compile(r'version (\d+(\.\d+)+)')

from metakernel import MetaKernel

class SASKernel(MetaKernel):
    #look at if '_usage.page_guiref' in code: in metakernel
    implementation = 'sas_kernel'
    implementation_version = '1.0'
    language = 'go'
    language_version = '0.1'
    banner = "SAS Kernel"
    print("at language info")
    language_info = {'name': 'go',
                     'file_extension': '.go',
                     'pygments_lexer': 'go'
                     #'codemirror_mode':{
                     #    'name':'sas'
                     #    }
                     }
    def __init__(self,**kwargs):
        #the filepath below assumes that the json files are in the same directory as the kernel.py
        #which should be fine since they will be delivered as part of the pip module
        with open(os.path.dirname(os.path.realpath(__file__))+'/'+'sasproclist.json') as proclist:
            self.proclist=json.load(proclist)
        with open(os.path.dirname(os.path.realpath(__file__))+'/'+'sasgrammerdictionary.json') as compglo:
            self.compglo=json.load(compglo)
        self.strproclist='\n'.join(str(x) for x in self.proclist)
        MetaKernel.__init__(self, **kwargs)
        self.mva = None
        #print("_start_sas")
        self._start_sas()

    def get_usage(self):
        return "This is the SAS kernel."

    def _start_sas(self):
        # Signal handlers are inherited by forked processes, and we can't easily
        # reset it from the subprocess. Since kernelapp ignores SIGINT except in
        # message handlers, we need to temporarily reset the SIGINT handler here
        # so that SAS and its children are interruptible.
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        python_path=shutil.which("python3.4")
        try:
            # start a SAS session within python bound to the shell session
            import saspy as saspy
            self.mva=saspy.SAS_session()
            self.mva._startsas()
            #print("leaving start_sas")
        finally:
            signal.signal(signal.SIGINT, sig)

    def do_execute_direct(self, code):

        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        interrupted = False
        lst_len=30762 # the length of the html5 with no real listing output

        if re.match(r'endsas;',code):
            self.do_shutdown(False)


        try:
            logger.debug("code type: " +str(type(code)))
            logger.debug("code length: " + str(len(code)))
            logger.debug("code string: "+ code)
            res=self.mva.submit(code)
            logger.debug("res type: " + str(type(res)))
            output=res['LST']
            log=res['LOG']
        except (KeyboardInterrupt, SystemExit):
            print ("keyboard interput by user")
            raise

        except :
            print("Exception Block:", sys.exc_info()[0])
            

        logger.debug("FULL LST: " + output)
        logger.debug("LST Length: " + str(len(output)))
        '''

        except EOF:
            output = self.saswrapper.child.before + 'Restarting SAS'
            self._start_sas()
        '''
        output = output.replace('\\n', chr(10)).replace('\\r',chr(ord('\r'))).replace('\\t',chr(ord('\t'))).replace('\\f',chr(ord('\f')))
        log    = log.replace('\\n', chr(10)).replace('\\r',chr(ord('\r'))).replace('\\t',        chr(ord('\t'))).replace('\\f',chr(ord('\f')))
        output=output[0:3].replace('\'',chr(00))+output[3:-4]+output[-4:].replace('\'',chr(00))
        log=log[0:3].replace('\'',chr(00))+log[3:-4]+log[-4:].replace('\'',chr(00))
        logger.debug("LOG: " + str(log))
        logger.debug("FULL LST: " +str(output))
        logger.debug("LOG Length: " + str(len(log)))
        logger.debug("LST Length: (html,stripped)" + str(len(output)) +","+ str(len(output)-lst_len))
        
        #Are there errors in the log? if show the 6 lines on each side of the error
        lines=re.split(r'[\n]\s*',log)
        i=0
        elog=[]
        debug1=0
        for line in lines:
            #logger.debug("In lines loop")
            i+=1
            if line.startswith('ERROR'):
                logger.debug("In ERROR Condition")
                elog=lines[(max(i-5,0)):(min(i+6,len(lines)))]
        tlog='\n'.join(elog)
        logger.debug("elog count: "+str(len(elog))) 
        logger.debug("tlog: " +str(tlog))
        if len(elog)==0 and len(output)>lst_len: #no error and LST output
            debug1=1
            logger.debug("DEBUG1: " +str(debug1)+ " no error and LST output ")
            return HTML(output)
        elif len(elog)==0 and len(output)<=lst_len: #no error and no LST
            debug1=2
            logger.debug("DEBUG1: " +str(debug1)+ " no error and no LST")
            return print(log)
        elif len(elog)>0 and len(output)<=lst_len: #error and no LST
            debug1=3
            logger.debug("DEBUG1: " +str(debug1)+ " error and no LST")
            return print(tlog)
        else: #errors and LST
            debug1=4
            logger.debug("DEBUG1: " +str(debug1)+ " errors and LST")
            return print(tlog),HTML(output)

    #Get code complete file from EG for this
    def get_completions(self,info):
        #print('debug test')
        #pprint(info)
        if info['line_num']>1:
            relstart=info['column']-(info['help_pos']-info['start'])
        else:
            relstart=info['start']
        seg=info['line'][:relstart]
        if relstart>0 and re.match('(?i)proc',seg.rsplit(None, 1)[-1]):
            #taking the path ro proclist
            #potentials=re.findall('(?i)'+info['obj']+'\W\w+',self.strproclist)
            potentials=re.findall('(?i)^'+info['obj']+'.*',self.strproclist,re.MULTILINE)
            return potentials
        else:
            #we are in the middle we should determine if it is "foop" or "foos"
            lastproc=info['code'].lower()[:info['help_pos']].rfind('proc')
            lastdata=info['code'].lower()[:info['help_pos']].rfind('data ')
            proc=False
            data=False
            if lastproc+lastdata==-2:
                somewhereelse=True
            else:
                if lastproc>lastdata: 
                    proc=True
                else: 
                    data=True
            

            if proc:
                #we are not in data section should see if proc option or statement
                lastsemi=info['code'].rfind(';')
                mykey='s'
                if lastproc>lastsemi:
                    mykey='p'
                procer=re.search('(?i)proc\s\w+',info['code'][lastproc:])
                method=procer.group(0).split(' ')[-1].upper()+mykey
                #procpos=info.['code'][lastsemi+1:info['start']].rfind(wehaveproc[0])
                mylist=self.compglo[method][0]
                #print(mylist,len(mylist))
                #potentials=re.findall('(?i)'+info['obj']+'\w+',' '.join(str(x) for x in mylist))
                potentials=re.findall('(?i)'+info['obj']+'.+','\n'.join(str(x) for x in mylist),re.MULTILINE)
                #print (info['obj'], potentials)
                return potentials
            elif data:
                #we are in statements (probably if there is no data)
                #assuming we are in the middle of the code
                
                lastsemi=info['code'].rfind(';')
                mykey='s'
                if lastproc>lastsemi:
                    mykey='p'
                mylist=self.compglo['DATA'+mykey][0]
                #potentials=re.findall('(?i)'+info['obj']+'\w+',' '.join(str(x) for x in mylist))
                potentials=re.findall('(?i)^'+info['obj']+'.*','\n'.join(str(x) for x in mylist),re.MULTILINE)
                #pprint(potentials)
                return potentials
        #keep in mind lin_num
            
        #list=['proc','print','optmodel','data']
        #potentials=get_close_matches(info['obj'],list)
            else:
                potentials=['']    
                return potentials
    '''
    def _get_right_list(s):
        proc_opt  = re.search(r"proc\s(\w+).*?[^;]\Z", s, re.IGNORECASE|re.MULTILINE)
        proc_stmt = re.search(r"\s*proc\s*(\w+).*;.*\Z", s, re.IGNORECASE|re.MULTILINE)
        data_opt  = re.search(r"\s*data\s*[^=].*[^;]?.*$", s, re.IGNORECASE|re.MULTILINE)
        data_stmt = re.search(r"\s*data\s*[^=].*[^;]?.*$", s, re.IGNORECASE|re.MULTILINE)
        print (s)
        if proc_opt:
        #logger.debug(proc_opt.group(1).upper()+'p')
            return (proc_opt.group(1).upper()+'p')
        #print(proc_opt.group('last'))
        elif proc_stmt:
        #logger.debug(proc_stmt.group(1).upper()+'s')
            return (proc_stmt.group(1).upper()+'s')
        elif data_opt:
        #logger.debug("data step")
            return ('DATA'+'p')
        elif data_stmt:
        #logger.debug("data step")
            return ('DATA'+'s')
        else:
            return(None)
    '''


    # def do_complete(self, code, cursor_pos):
    #     code = code[:cursor_pos]
    #     default = {'matches': [], 'cursor_start': 0,
    #                'cursor_end': cursor_pos, 'metadata': dict(),
    #                'status': 'ok'}

    #     if not code or code[-1] == ' ':
    #         return default

    #     tokens = code.replace(';', ' ').split()
    #     if not tokens:
    #         return default

    #     matches = []
    #     token = tokens[-1]
    #     start = cursor_pos - len(token)

    #     if token[0] == '$':
    #         # complete variables
    #         cmd = 'compgen -A arrayvar -A export -A variable %s' % token[1:] # strip leading $
    #         output = self.saswrapper.run_command(cmd).rstrip()
    #         completions = set(output.split())
    #         # append matches including leading $
    #         matches.extend(['$'+c for c in completions])
    #     else:
    #         # complete functions and builtins
    #         cmd = 'compgen -cdfa %s' % token
    #         output = self.saswrapper.run_command(cmd).rstrip()
    #         matches.extend(output.split())

    #     if not matches:
    #         return default
    #     matches = [m for m in matches if m.startswith(token)]

    #     return {'matches': sorted(matches), 'cursor_start': start,
    #             'cursor_end': cursor_pos, 'metadata': dict(),
    #             'status': 'ok'}

    def do_shutdown(self,restart):
        """
        Shut down the app gracefully, saving history.
        """
        print ("in shutdown function")
        if self.hist_file:
            with open(self.hist_file, 'wb') as fid:
                data = '\n'.join(self.hist_cache[-self.max_hist_cache:])
                fid.write(data.encode('utf-8'))
        if restart:
            self.Print("Restarting kernel...")
            self.reload_magics()
            self.restart_kernel()
            self.Print("Done!")
        return {'status': 'ok', 'restart': restart}
        #if restart:
        #    self.saswrapper.run_command('mva._submit(";endsas;")')
