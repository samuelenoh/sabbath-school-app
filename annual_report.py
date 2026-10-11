"""Privacy-conscious annual summaries built solely from recorded departmental data."""
from collections import Counter, defaultdict
from programme import programme_summary

STATUSES=('Requested','Ordered','Received','Distributed','Cancelled')

def build_annual_report(data, attendance, year, include_finance):
    start,end=f'{year}-01-01',f'{year}-12-31'
    dated=lambda rows:[r for r in rows if start<=r.get('day','')<=end]
    def attendance_summary(rows):
        n=len(rows);counts=Counter(r['status'] for r in rows)
        return {'recorded_sabbaths':len({r['day'] for r in rows}),'marked_entries':n,'present':counts['Present'],'absent':counts['Absent'],'excused':counts['Excused'],'studied':sum(bool(r['study']) for r in rows),'present_percent':round(counts['Present']*100/n,1) if n else None}
    def giving_summary(rows):
        totals=defaultdict(int);contributions=defaultdict(int);categories=defaultdict(int)
        for r in rows:
            totals[r['currency']]+=r['amount_minor'];categories[(r['currency'],r['category'])]+=r['amount_minor']
            if r['category']=='Class contribution':contributions[r['currency']]+=r['amount_minor']
        return {'record_count':len(rows),'totals':[{'currency':k,'amount_minor':v} for k,v in sorted(totals.items())],'class_contributions':[{'currency':k,'amount_minor':v} for k,v in sorted(contributions.items())],'categories':[{'currency':c,'category':k,'amount_minor':v} for (c,k),v in sorted(categories.items())]}
    def books_summary(rows):
        qty={s:sum(r['quantity'] for r in rows if r['status']==s) for s in STATUSES}
        return {'record_count':len(rows),'active_quantity':sum(v for k,v in qty.items() if k!='Cancelled'),'quantity_by_status':qty}
    members=data['members'];classes=data['classes'];att=dated(attendance);lessons=dated(data['lessons']);events=dated(data['events']);outreach=dated(data['outreach']);books=[r for r in data['bookorders'] if r['year']==year];offers=dated(data['offerings']) if include_finance else []
    programmes=dated(data.get('programmes',[]))
    report={'year':year,'period':{'start':start,'end':end},'scope':'Whole Sabbath School department','membership':{'current_total':len(members),'current_active':sum(r['status']=='Active' for r in members),'current_visitors':sum(r['status']=='Visitor' for r in members),'current_inactive':sum(r['status']=='Inactive' for r in members),'recorded_join_dates_in_year':sum(start<=r.get('joined_on','')<=end for r in members)},'classes':{'current_total':len(classes),'current_active':sum(bool(r['active']) for r in classes),'current_assigned_teachers':len({r['teacher_id'] for r in classes if r['active'] and r.get('teacher_id') is not None})},'attendance':attendance_summary(att),'lessons':{'recorded_lessons':len(lessons)},'books':books_summary(books),'events':{'recorded_events':len(events),'current_registration_entries':sum(len(r.get('registrations',[])) for r in events)},'outreach':{'recorded_activities':len(outreach),'completed_activities':sum(r['status']=='Completed' for r in outreach),'reported_people_reached_completed':sum(r['people_reached'] for r in outreach if r['status']=='Completed')},'programme':programme_summary(programmes),'financial_access':include_finance,'giving':giving_summary(offers) if include_finance else None,'class_breakdown':[],'quarters':[],'book_breakdown':[], 'limitations':['Membership and class counts describe the current roster, not a historical year-end snapshot. Deleted members and historical transfers cannot be reconstructed.','Recorded join dates count current records with a join date in the selected year; they are not a complete historical membership-change ledger.','Attendance covers marked entries only, including excused in the percentage denominator; missing entries and unrecorded Sabbaths are not inferred.','Lesson records are preparation material; study completion is self-reported through attendance.','Giving includes each offering once; class contributions are a subset, not an additional total. Missing records do not prove no giving. Amounts use two decimal minor units and remain separated by currency.','Book quantities describe current tracking statuses for orders labelled with the selected year and quarter; there are no historical status timestamps or supplier/payment records.','Events are recorded plans and current registrations, not verified event attendance or evidence of completed activities.','Outreach reach is reported for completed activities and may count the same person more than once.','Weekly programme counts reflect recorded statuses only; cancelled weeks are excluded from activity counts. Names, assignments and activity notes are kept in internal weekly records, not this shareable report. Local initiative labels are retained without assumed definitions. Reassembly discussion contributions are not financial giving.','Notes, member names, phone numbers and email addresses are omitted from this shareable report.']}
    for cls in classes:
        cid=cls['id'];roster=[r for r in members if r['class_id']==cid]
        row={'class_name':cls['name'],'current_roster':len(roster),'current_active':sum(r['status']=='Active' for r in roster),'current_visitors':sum(r['status']=='Visitor' for r in roster),'attendance':attendance_summary([r for r in att if r['class_id']==cid]),'recorded_lessons':sum(r['class_id']==cid for r in lessons),'books':books_summary([r for r in books if r['class_id']==cid]),'completed_outreach':sum(r['class_id']==cid and r['status']=='Completed' for r in outreach)}
        if include_finance:row['giving']=giving_summary([r for r in offers if r['class_id']==cid])
        report['class_breakdown'].append(row)
    for q in range(1,5):
        quarter=lambda rows:[r for r in rows if (int(r['day'][5:7])-1)//3+1==q]
        qa=quarter(att);qo=quarter(outreach)
        row={'quarter':q,'programme':programme_summary(quarter(programmes)),'attendance':attendance_summary(qa),'recorded_lessons':len(quarter(lessons)),'books':books_summary([r for r in books if r['quarter']==q]),'recorded_events':len(quarter(events)),'completed_outreach':sum(r['status']=='Completed' for r in qo),'reported_people_reached_completed':sum(r['people_reached'] for r in qo if r['status']=='Completed')}
        if include_finance:row['giving']=giving_summary(quarter(offers))
        report['quarters'].append(row)
    names={r['id']:r['name'] for r in classes}
    grouped=defaultdict(Counter)
    for r in books:grouped[(names.get(r['class_id'],'Archived class'),r['quarter'],r['book_title'])][r['status']]+=r['quantity']
    report['book_breakdown']=[{'class_name':c,'quarter':q,'book_title':t,'quantity_by_status':{s:counts[s] for s in STATUSES}} for (c,q,t),counts in sorted(grouped.items())]
    return report
