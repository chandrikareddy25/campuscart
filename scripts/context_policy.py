"""Explicit decision policy. Deferral is never treated as release acceptance."""

def decide(evidence):
    status=evidence.get('status')
    if status=='passed':
        return {'action':'accept','classification':'verified_transaction','reason':'Valid checkout and integrity checks passed'}
    if evidence.get('cleanup_failed'):
        return {'action':'defer','classification':'cleanup_unresolved','reason':'Inspect the test order before retrying'}
    if evidence.get('kind')=='business_precondition':
        return {'action':'defer','classification':'business_constraint','reason':'A valid checkout could not be exercised; do not promote this release'}
    if evidence.get('kind')=='integrity':
        return {'action':'reject','classification':'integrity_violation','reason':'A transaction invariant failed'}
    if evidence.get('kind')=='http':
        code=evidence.get('http_status',0)
        if code in (401,403):
            return {'action':'defer','classification':'authentication_uncertain','reason':'Credentials or authentication behaviour need investigation'}
        if code in (429,502,503,504) or evidence.get('dependency_ready') is False:
            return {'action':'retry','classification':'dependency_or_capacity_uncertain','reason':'Retry within a bounded window; do not attribute this to the release yet'}
        if code==409:
            # Never exempt every conflict: state must independently support the rejection.
            return {'action':'defer' if evidence.get('constraint_confirmed') else 'reject','classification':'business_constraint' if evidence.get('constraint_confirmed') else 'unexpected_conflict','reason':'Observed checkout state supports rejection' if evidence.get('constraint_confirmed') else 'Valid checkout unexpectedly rejected'}
        return {'action':'reject','classification':'unexpected_http_failure','reason':'Request failed despite a valid transaction fixture'}
    return {'action':'retry','classification':'insufficient_evidence','reason':'Retry boundedly; unresolved errors remain deferred'}

def compare(evidence,healthy=True):
    return {
        'health_only':'accept' if healthy else 'reject',
        'existing_guard':'reject' if evidence.get('observations') else ('accept' if evidence.get('status')=='passed' else ('reject' if evidence.get('status')=='failed' else 'defer')),
        'contextual_guard':decide(evidence)['action'],
    }
