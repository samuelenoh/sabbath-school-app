"""Preview or atomically import a reviewed private roster CSV into an existing class.

Run against a backed-up database with the web app stopped. No accounts, attendance,
offerings or WhatsApp consent are created. CSV contents are never printed to logs.
"""
import argparse,csv,json,re
from pathlib import Path
import server

def normalize_phone(source):
    if not source: return ''
    compact=re.sub(r'[\s()-]','',source)
    if re.fullmatch(r'0\d{9}',compact): return '+233'+compact[1:]
    if re.fullmatch(r'\+[1-9]\d{7,14}',compact): return compact
    raise ValueError('Phone needs review: expected a Ghana local number or international format.')

def prepare_import(c,rows,class_id):
    server.record(c,class_id,'classes')
    existing=server.records(c,'members'); seen=[];plan=[]
    for number,row in enumerate(rows,1):
        data={'name':row.get('name',''),'residence':row.get('residence',''),
              'phone_local':row.get('phone_local',''),'phone':normalize_phone(row.get('phone_local','')),
              'class_office':row.get('class_office',''),'class_id':class_id,'status':'Active',
              'email':'','birthday':'','joined_on_unknown':True,'whatsapp_opt_in':False,
              'notes':row.get('notes','')}
        clean=server.validate(c,'members',data,{'role':'admin','id':0})
        matches=[m for m in existing+seen if m['class_id']==class_id and m['name'].casefold()==clean['name'].casefold() and m.get('phone','')==clean['phone']]
        conflicts=[m for m in existing+seen if m['name'].casefold()==clean['name'].casefold() or (clean['phone'] and m.get('phone')==clean['phone'])]
        if matches:
            match=matches[0]
            changed=any(match.get(k,'')!=clean.get(k,'') for k in ('residence','class_office','phone_local'))
            action='review_conflict' if changed else 'skip_existing'
        else: action='review_conflict' if conflicts else 'insert'
        plan.append({'row':number,'action':action,'data':clean})
        if action=='insert':seen.append(clean)
    return plan

def import_rows(rows,class_id,apply=False):
    with server.connect() as c:
        c.execute('BEGIN IMMEDIATE');plan=prepare_import(c,rows,class_id)
        conflicts=[r['row'] for r in plan if r['action']=='review_conflict']
        if apply and conflicts: raise ValueError('Import blocked by conflicting rows: '+', '.join(map(str,conflicts)))
        if apply:
            for item in plan:
                if item['action']=='insert':
                    ident=c.execute('INSERT INTO records(module,data) VALUES(?,?)',('members',json.dumps(item['data']))).lastrowid
                    item['member_id']=ident
            server.audit(c,None,'members.roster_import',{'class_id':class_id,'inserted':sum(p['action']=='insert' for p in plan),'skipped':sum(p['action']=='skip_existing' for p in plan)})
        return plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file',type=Path);parser.add_argument('--class-id',type=int,required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--preview-file',type=Path)
    args=parser.parse_args()
    with args.csv_file.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if args.preview_file and args.preview_file.exists(): raise ValueError('Preview file exists; choose a new output file to retain the earlier review.')
    plan=import_rows(rows,args.class_id,args.apply)
    if args.preview_file:
        args.preview_file.parent.mkdir(parents=True,exist_ok=True)
        args.preview_file.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'applied':args.apply,'rows':len(plan),'insert':sum(p['action']=='insert' for p in plan),
          'skip_existing':sum(p['action']=='skip_existing' for p in plan),'conflicts':sum(p['action']=='review_conflict' for p in plan)}))

if __name__=='__main__':main()
