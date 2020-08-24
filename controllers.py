"""
This file defines actions, i.e. functions the URLs are mapped into
The @action(path) decorator exposed the function at URL:

    http://127.0.0.1:8000/{app_name}/{path}

If app_name == '_default' then simply

    http://127.0.0.1:8000/{path}

If path == 'index' it can be omitted:

    http://127.0.0.1:8000/

The path follows the bottlepy syntax.

@action.uses('generic.html')  indicates that the action uses the generic.html template
@action.uses(session)         indicates that the action uses the session
@action.uses(db)              indicates that the action uses the db
@action.uses(T)               indicates that the action uses the i18n & pluralization
@action.uses(auth.user)       indicates that the action requires a logged in user
@action.uses(auth)            indicates that the action requires the auth object

session, db, T, auth, and tempates are examples of Fixtures.
Warning: Fixtures MUST be declared with @action.uses({fixtures}) else your app will result in undefined behavior
"""

import uuid

from py4web import action, request, abort, redirect, URL, Field
from py4web.utils.form import Form, FormStyleBulma
from py4web.utils.url_signer import URLSigner

from yatl.helpers import A

from . common import db, session, T, cache, auth, signed_url
from pydal.validators import *

url_signer = URLSigner(session)

# The auth.user below forces login.
@action('index', method='GET')
@action.uses(db, session, auth.user, 'index.html')
def index():
    user = auth.get_user()
    rows = db(db.person.user_email==auth.current_user.get('email')).select().as_list()
    for row in rows:
        # get phone numbers associated with contact person
        sub_rows = db(db.phone.person_id==row.get('id')).select().as_list()
        s = ""
        count = 0
        # construct string & assign to row
        for r in sub_rows:
            if count > 0:
                s = s + ", "
            s = s + r.get('number') + " (" + r.get('kind') + ")"
            row['phone_numbers'] = s
            count = count + 1
        # if no phone numbers exist
        if count == 0:
            row['phone_numbers'] = ""
    return dict(rows=rows, url_signer=url_signer)

@action('add_contact', method=['GET', 'POST'])
@action.uses(db, session, auth.user, 'add_contact.html')
def add_contact():
    form = Form([
        Field('first_name', requires=IS_NOT_EMPTY()),
        Field('last_name', requires=IS_NOT_EMPTY())],
        csrf_session=session, formstyle=FormStyleBulma)
    if form.accepted:
        db.person.insert(
            first_name=form.vars.get('first_name'),
            last_name=form.vars.get('last_name'),
            phone_numbers="")
        redirect(URL('index'))
    return dict(form=form)

@action('edit_contact/<person_id>', method=['GET', 'POST'])
@action.uses(db, session, auth.user, 'add_contact.html')
def edit_contact(person_id=None):
    # read person
    p = db.person[person_id]
    if p is None:
        # nothing to edit
        redirect(URL('index'))
    # contact wasn't the created by the user
    if (p.user_email!=auth.current_user.get('email')):
        redirect(URL('index'))
    else:
        row = db(db.person.id == person_id).select().as_list()
        form = Form(
            [Field('first_name', requires=IS_NOT_EMPTY()),
             Field('last_name', requires=IS_NOT_EMPTY())],
            record=dict(first_name=row[0].get('first_name'), last_name=row[0].get('last_name')),
            deletable=False,
            csrf_session=session,
            formstyle=FormStyleBulma)
        if form.accepted:
            db.person.update_or_insert(
                ((db.person.id == person_id)),
                first_name=form.vars.get('first_name'),
                last_name=form.vars.get('last_name'))
            redirect(URL('index'))
        return dict(form=form)

@action('delete_contact/<person_id>', method='GET')
@action.uses('index.html', session, db, url_signer.verify())
def delete_contact(person_id=None):
    p = db.person[person_id]
    if p is None:
        redirect(URL('index'))
    # else delete person if has access
    if (p.user_email==auth.current_user.get('email')):
        db(db.person.id == person_id).delete()
    redirect(URL('index'))

# after pressing Edit button in index - table with phone numbers
@action('edit_phones/<person_id>', method='GET')
@action.uses(db, session, auth.user, 'phone.html')
def edit_phones(person_id=None):
    p = db.person[person_id]
    contact_person = p.first_name + " " + p.last_name
    user_email = p.user_email
    if p is None:
        redirect(URL('index'))
    if (p.user_email!=auth.current_user.get('email')):
        redirect(URL('index'))
    else:
        rows = db(db.phone.person_id==p.id).select()
        return dict(rows=rows, url_signer=url_signer,
                    contact_person=contact_person,
                    person_id=person_id,
                    user_email=user_email)

# after pressing add phone number - blank form
@action('add_number/<person_id>', method=['GET', 'POST'])
@action.uses(db, session, auth.user, 'add_number.html')
def add_number(person_id=None):
    # read person
    p = db.person[person_id]
    if (p.user_email!=auth.current_user.get('email')):
        redirect(URL('index'))
    else:
        form = Form([
            Field('number', requires=IS_NOT_EMPTY()),
            Field('kind', requires=IS_NOT_EMPTY())],
            csrf_session=session,
            formstyle=FormStyleBulma)
        if form.accepted:
            db.phone.insert(
                person_id=person_id,
                number=form.vars.get('number'),
                kind=form.vars.get('kind'))
            redirect(URL('edit_phones', person_id))
        # return variables
        row = db(db.person.id == person_id).select().as_list()
        first_name = row[0].get('first_name')
        last_name = row[0].get('last_name')
        return dict(form=form, first_name=first_name, last_name=last_name)

# edit a phone number from phone page
@action('edit_number/<person_id>/<phone_id>', method=['GET', 'POST'])
@action.uses(db, session, auth.user, 'add_number.html')
def edit_contact(person_id=None, phone_id=None):
    # read person
    p = db.person[person_id]
    if p is None:
        # nothing to edit
        redirect(URL('index'))
    # contact wasn't the created by the user
    if (p.user_email!=auth.current_user.get('email')):
        redirect(URL('index'))
    else:
        row = db(db.phone.id == phone_id).select().as_list()
        form = Form(
            [Field('number'),
             Field('kind')],
            record=dict(number=row[0].get('number'), kind=row[0].get('kind')),
            deletable=False,
            csrf_session=session,
            formstyle=FormStyleBulma)
        if form.accepted:
            db.phone.update_or_insert(
                ((db.phone.id==phone_id)),
                number=form.vars.get('number'),
                kind=form.vars.get('kind'))
            redirect(URL('edit_phones', person_id))
        # return variables
        person_row = db(db.person.id == person_id).select().as_list()
        first_name = person_row[0].get('first_name')
        last_name = person_row[0].get('last_name')
        return dict(form=form, first_name=first_name, last_name=last_name)

# delete phone number from phone page
@action('delete_number/<person_id>/<phone_id>', method='GET')
@action.uses('index.html', session, db, url_signer.verify())
def delete_contact(person_id=None, phone_id=None):
    p = db.person[person_id]
    if p is None:
        redirect(URL('index'))
    # else delete person if has access
    if (p.user_email==auth.current_user.get('email')):
        db(db.phone.id == phone_id).delete()
    redirect(URL('edit_phones', person_id))
