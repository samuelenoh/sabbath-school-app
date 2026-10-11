"""Reusable local programme outline and truthful recorded activity summaries."""
from collections import Counter
import hashlib, json

LOCAL_OUTLINE = [
    'Into My Heart / prayer', 'Introduction of facilitators', 'Opening hymn',
    'Opening prayer', 'Welcome song',
    'Special song (quartet, individuals, Seraphim choir, youth choir, etc.)',
    'Mission reading', 'Sabbath School retrospect', 'Dispersal into classes',
    'Reassembly / questions and contributions',
    'Friend for the Year, Read a Chapter a Day, and Gethsemane Hour',
    'Secretary report', 'Closing hymn', 'Closing prayer'
]

def default_template():
    return {'version':1, 'name':'Effiakuma Sabbath School programme', 'items':[
        {'key':str(i+1),'label':label,'time':'','member_ids':[],'responsible_names':[],
         'status':'Planned','notes':''} for i,label in enumerate(LOCAL_OUTLINE)]}

def assignment_fingerprint(programme):
    # Completion/care notes never trigger another assignment notification.
    payload={'day':programme['day'],'cancelled':programme['status']=='Cancelled',
             'items':[{k:r[k] for k in ('key','label','time','member_ids')} for r in programme['items']]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]

def assignment_previews(programme,members):
    by_id={m['id']:m for m in members}; grouped={}
    for item in programme['items']:
        for mid in item['member_ids']:
            grouped.setdefault(mid,[]).append(item['label']+(f" at {item['time']}" if item['time'] else ''))
    result=[]
    for mid,labels in grouped.items():
        m=by_id.get(mid); name=m['name'] if m else 'Unavailable recipient'
        activities='; '.join(labels)
        reason=''
        if programme['status']=='Cancelled': reason='Programme cancelled'
        elif not m or m.get('status')=='Inactive': reason='Recipient unavailable or inactive'
        elif not m.get('phone'): reason='No international phone number'
        elif not m.get('whatsapp_opt_in'): reason='WhatsApp consent not recorded'
        elif len(activities)>1000: reason='Assignment summary exceeds the template parameter limit; shorten activity labels'
        parameters=[name,programme['day'],activities]
        result.append({'member_id':mid,'name':name,'activities':activities,'eligible':not reason,
            'reason':reason,'parameters':parameters,
            'message':f"Hello {name}, your Sabbath School assignments for {programme['day']}: {activities}. Please confirm with the secretary."})
    return result

def programme_summary(rows):
    active=[p for p in rows if p['status']!='Cancelled']
    items=[item for p in active for item in p['items']]
    labels=Counter(item['label'] for item in items if item['status']=='Completed')
    return {'recorded_weeks':len(rows),'completed_weeks':sum(p['status']=='Completed' for p in rows),
        'cancelled_weeks':sum(p['status']=='Cancelled' for p in rows),
        'scheduled_items':len(items),'completed_items':sum(i['status']=='Completed' for i in items),
        'skipped_items':sum(i['status']=='Skipped' for i in items),
        'assigned_item_slots':sum(len(i['member_ids']) for i in items),
        'completed_activity_labels':[{'label':label,'count':n} for label,n in sorted(labels.items())]}
