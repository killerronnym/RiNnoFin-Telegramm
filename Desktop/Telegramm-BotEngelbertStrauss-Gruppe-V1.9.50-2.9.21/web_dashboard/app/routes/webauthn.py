from flask import Blueprint, request, jsonify, session
from flask_login import current_user, login_required, login_user
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response
)
from webauthn.helpers.structs import (
    RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
    UserVerificationRequirement
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes, options_to_json
import os
import json
from ..models import db, User, PasskeyCredential

bp = Blueprint('webauthn', __name__, url_prefix='/webauthn')

RP_NAME = 'Bot Steuerung Dashboard'

def get_rp_id():
    return request.host.split(':')[0]

def get_origin():
    return request.host_url.rstrip('/')

@bp.route('/register/generate', methods=['POST'])
@login_required
def generate_registration():
    try:
        user_id_str = str(current_user.id)
        
        # Holen aller existierenden Credentials für den Nutzer
        existing_credentials = PasskeyCredential.query.filter_by(user_id=current_user.id).all()
        exclude_credentials = [{"id": base64url_to_bytes(cred.credential_id), "type": "public-key"} for cred in existing_credentials]
        
        options = generate_registration_options(
            rp_id=get_rp_id(),
            rp_name=RP_NAME,
            user_id=user_id_str.encode('utf-8'),
            user_name=current_user.username,
            user_display_name=current_user.username,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM, # Passkeys
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.PREFERRED
            ),
            exclude_credentials=exclude_credentials
        )
        
        # Speichere Challenge in der Session
        session['webauthn_registration_challenge'] = bytes_to_base64url(options.challenge)
        
        return jsonify(json.loads(options_to_json(options)))
    except Exception as e:
        print("Error generating registration:", str(e))
        return jsonify({"error": str(e)}), 400

@bp.route('/register/verify', methods=['POST'])
@login_required
def verify_registration():
    try:
        credential = request.json
        expected_challenge = session.get('webauthn_registration_challenge')
        
        if not expected_challenge:
            return jsonify({"error": "No challenge found"}), 400
            
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            require_user_verification=False
        )
        
        # Credential speichern
        new_cred = PasskeyCredential(
            user_id=current_user.id,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count
        )
        db.session.add(new_cred)
        db.session.commit()
        
        session.pop('webauthn_registration_challenge', None)
        return jsonify({"success": True})
        
    except Exception as e:
        print("Error verifying registration:", str(e))
        return jsonify({"error": str(e)}), 400

@bp.route('/login/generate', methods=['POST'])
def generate_authentication():
    try:
        # Hier können wir entweder username-basiert arbeiten oder passwortless
        # Für Passwordless fragen wir keine credentials ab, sondern lassen den Browser entscheiden
        username = request.json.get('username')
        user = None
        allow_credentials = []
        
        if username:
            user = User.query.filter_by(username=username).first()
            if user:
                creds = PasskeyCredential.query.filter_by(user_id=user.id).all()
                allow_credentials = [{"id": base64url_to_bytes(cred.credential_id), "type": "public-key"} for cred in creds]
        
        options = generate_authentication_options(
            rp_id=get_rp_id(),
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED
        )
        
        session['webauthn_authentication_challenge'] = bytes_to_base64url(options.challenge)
        if user:
            session['webauthn_login_user_id'] = user.id
            
        return jsonify(json.loads(options_to_json(options)))
    except Exception as e:
        print("Error generating auth:", str(e))
        return jsonify({"error": str(e)}), 400

@bp.route('/login/verify', methods=['POST'])
def verify_authentication():
    try:
        credential = request.json
        expected_challenge = session.get('webauthn_authentication_challenge')
        
        if not expected_challenge:
            return jsonify({"error": "No challenge found"}), 400
            
        cred_id = credential.get('id')
        passkey = PasskeyCredential.query.filter_by(credential_id=cred_id).first()
        
        if not passkey:
            return jsonify({"error": "Credential not found in DB"}), 400
            
        user = User.query.get(passkey.user_id)
        if not user:
            return jsonify({"error": "User not found"}), 400
            
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=False
        )
        
        # Update sign count
        passkey.sign_count = verification.new_sign_count
        db.session.commit()
        
        session.pop('webauthn_authentication_challenge', None)
        
        # Login the user
        login_user(user)
        return jsonify({"success": True, "redirect": "/"})
        
    except Exception as e:
        print("Error verifying auth:", str(e))
        return jsonify({"error": str(e)}), 400
