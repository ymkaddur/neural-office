import argparse
import json
import os
from pathlib import Path
import sys
import uuid

from . import __version__
from .ledger import Ledger,Denied,canonical,digest
from .ollama import local_metadata,select_model
from .runner import run,recover


def snapshot_file(file,root):
    from .files import capture_html
    return capture_html(file,root)


def main(argv=None):
    parser=argparse.ArgumentParser(description=f'Neural Office {__version__} — local review engine for Windows')
    parser.add_argument('--version',action='version',version=__version__)
    parser.add_argument('--state',help='Office ledger; defaults to one per user. Preserve its witness when restoring.')
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('init'); sub.add_parser('status'); sub.add_parser('models'); sub.add_parser('gui')
    plan = sub.add_parser('office-plan', help='Describe the three-round office without executing it')
    plan.add_argument('--objective', required=True)
    office = sub.add_parser('office-start', help='Authorize a fixed static HTML review and reserve one project attempt')
    for name in ('project', 'thread', 'root', 'file', 'key'):
        office.add_argument('--' + name, required=True)
    office.add_argument('--objective', required=True, help='Recorded instruction for this static HTML review')
    office.add_argument('--max-dispatches', type=int, choices=range(1, 7), default=3)
    office.add_argument('--tries-per-step', type=int, choices=(1, 2), default=1)
    lookup = sub.add_parser('office-lookup', help='Reopen a reservation by project, thread and original request key')
    for name in ('project', 'thread', 'key'):
        lookup.add_argument('--' + name, required=True)
    commands = {'office-step': 'Dispatch one authorized step by its ID',
                'office-show': 'Read the durable state, next action and remaining balance',
                'office-reconcile': 'Resolve an interrupted delivery without starting a receiver',
                'office-output': 'Read a confirmed result and its input receipt identities'}
    for name, description in commands.items():
        command = sub.add_parser(name, help=description)
        command.add_argument('attempt')
        if name in ('office-step', 'office-output'):
            command.add_argument('step')
    check=sub.add_parser('check',help='Static HTML findings only: no model, ledger or inference')
    check.add_argument('--root',required=True); check.add_argument('--file',required=True)
    sub.add_parser('protect',help='Enroll an idle schema-1 V5.2 ledger without resetting history')
    for action in ('backup','restore'):
        command=sub.add_parser(action, help=f'{action.capitalize()} the attempt ledger. Captures, inspection reports and the witness are stored separately.')
        command.add_argument('file', help='SQLite copy of the attempt ledger')
    for action in ('legacy-inspect','legacy-reconcile'):
        command=sub.add_parser(action); command.add_argument('source_root')
    command=sub.add_parser('legacy-rebind')
    command.add_argument('project'); command.add_argument('root')
    audit=sub.add_parser('audit')
    audit.add_argument('--project',required=True); audit.add_argument('--root',required=True)
    audit.add_argument('--file',required=True); audit.add_argument('--model',required=True)
    audit.add_argument('--roles',type=int,choices=(1,3,7),default=7)
    audit.add_argument('--objective',default='Audit the selected HTML snapshot and explain the observed static findings.')
    audit.add_argument('--key',default=None)
    for action in ('cancel','recover','report','resume'):
        command=sub.add_parser(action); command.add_argument('attempt')
    args=parser.parse_args(argv)
    if args.action == 'office-plan':
        from .office_plan import office_plan
        print(canonical(office_plan(args.objective)))
        return
    if args.action=='check':
        from .audit import make_report
        print(make_report(snapshot_file(args.file,args.root),[]).decode('utf-8')); return
    if args.action=='models':
        print(canonical({'models':[{'name':m['name'],'digest':m.get('digest'),'size':m.get('size')} for m in local_metadata()['models']]})); return
    ledger=Ledger(args.state)
    if args.action.startswith('office-'):
        from . import office_protocol as office
        if args.action == 'office-start':
            identity = office.start(ledger, args.project, args.thread, args.root, args.file, args.objective, args.key,
                                    args.max_dispatches, args.tries_per_step)
            result = office.status(ledger, identity)
        elif args.action == 'office-lookup':
            identity = office.lookup(ledger, args.project, args.thread, args.key)
            result = office.status(ledger, identity) if identity else {'found': False}
        elif args.action == 'office-step':
            result = office.run_step(ledger, args.attempt, args.step)
        elif args.action == 'office-reconcile':
            result = office.reconcile(ledger, args.attempt)
        elif args.action == 'office-output':
            result = office.output(ledger, args.attempt, args.step)
        else:
            result = office.status(ledger, args.attempt)
        print(canonical(result))
        return
    if args.action in ('protect','backup','restore'):
        from . import continuity
        operation=getattr(continuity,args.action)
        print(canonical(operation(ledger) if args.action=='protect' else operation(ledger,args.file))); return
    if args.action in ('legacy-inspect','legacy-reconcile','legacy-rebind'):
        from . import legacy
        if args.action=='legacy-inspect':
            with legacy.snapshot(args.source_root) as observed: print(canonical(observed))
        elif args.action=='legacy-reconcile': print(canonical(legacy.reconcile(ledger,args.source_root)))
        else:
            legacy.rebind(ledger,args.project,args.root)
            print(canonical({'rebound':True,'authority_granted':False,'budget_preserved':True}))
        return
    if args.action=='init': ledger.initialize(); print(canonical({'initialized':True,'version':__version__})); return
    if args.action=='gui':
        from .ui import show
        show(ledger); return
    if args.action=='status': print(canonical(ledger.status())); return
    if args.action=='cancel': print(canonical({'state':ledger.cancel(args.attempt)})); return
    if args.action=='recover': print(canonical({'state':recover(ledger,args.attempt)})); return
    if args.action=='report':
        row=ledger.attempt(args.attempt)
        if row['artifact'] is None: raise Denied('NO_REPORT_AVAILABLE')
        if row['state'] != 'ACCEPTED' or json.loads(row['verdict']).get('passed') is not True:
            raise Denied('REPORT_NOT_ACCEPTED')
        artifact = bytes(row['artifact'])
        if digest(artifact) != row['artifact_sha']: raise Denied('REPORT_CHANGED')
        print(artifact.decode('utf-8')); return
    if args.action=='resume':
        row=ledger.attempt(args.attempt)
        print(canonical({'attempt':args.attempt,'state':run(ledger,args.attempt,row['profile']['roles'])})); return
    profile=select_model(args.model,local_metadata()['models']); profile['roles']=args.roles
    content=snapshot_file(args.file,args.root)
    ledger.initialize(); ledger.register(args.project,args.root)
    key=args.key or uuid.uuid4().hex
    # Executing the audit command is the user's explicit admission action.
    # Admission and reservation share a transaction; replay cannot renew authority.
    attempt=ledger.reserve(args.project,args.objective,content,profile,key,admit=True)
    print(canonical({'attempt':attempt,'state':ledger.attempt(attempt)['state'],
                     'mode':profile['mode']}),flush=True)
    state=run(ledger,attempt,args.roles,progress=lambda role,state:print(canonical({'role':role,'state':state}),flush=True))
    print(canonical({'attempt':attempt,'state':state,'status':ledger.status()}))


if __name__=='__main__':
    try: main()
    except (Denied,OSError,ValueError,RuntimeError) as exc:
        print(canonical({'error':type(exc).__name__,'reason':str(exc)}),file=sys.stderr)
        raise SystemExit(2)
