import json
import requests
import xml.etree.ElementTree as ET
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from urllib.parse import quote
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .services import IAMService

# =====================
# Authentication Views
# =====================

def fetch_user_info(username):
    """Fetch user information from KKU service by username."""
    user_info_url = settings.KKU_SERVICES_USER_INFO_URL
    user_info_data = {
        "wsUsername": settings.KKU_SERVICES_USER,
        "wsPassword": settings.KKU_SERVICES_PASS,
        "nickname": username
    }
    user_info_response = requests.post(user_info_url, json=user_info_data)
    user_info = json.loads(user_info_response.content)
    return user_info

def cas_login(request, page_type):
    """CAS login view: redirects to CAS if no ticket, authenticates and logs in user if ticket is present."""
    ticket = request.GET.get('ticket')
    next_url = request.GET.get('next', '/index')
    service_url = f"{settings.MAIN_URL}/login/?next={next_url}"

    if not ticket:
        cas_login_url = (
            f"{settings.CAS_PROTOCOL}://{settings.CAS_HOST}{settings.CAS_CONTEXT}/login"
            f"?service={service_url}"
        )
        return HttpResponseRedirect(cas_login_url)

    user = authenticate(request, ticket=ticket, service=service_url)
    if user:
        login(request, user)
        return HttpResponseRedirect(next_url)
    else:
        return render(request, 'forbidden.html')

def cas_logout(request):
    """CAS logout view: logs out user and redirects to CAS logout."""
    logout(request)
    logout_url = f"{settings.CAS_PROTOCOL}://{settings.CAS_HOST}{settings.CAS_CONTEXT}/logout?service={quote(settings.MAIN_URL)}"
    return HttpResponseRedirect(logout_url)

# =====================
# IAM/Nafath Views
# =====================

def create_iam_req(request):
    """Initiate IAM/Nafath login request and redirect to IAM login page."""
    callback_url = 'https://certs.kku.edu.sa/iam_callback/'  # Hardcoded for production
    data = IAMService.get_data_via_ws('callbackUrl', callback_url, 'createIamReq')
    if data:
        return HttpResponseRedirect(data)
    else:
        return HttpResponse("Error initiating IAM request.", status=500)

@csrf_exempt
def iam_callback(request):
    """IAM/Nafath callback view: handles SAML response, creates/updates user, and logs in."""
    saml_response = request.POST.get('SAMLResponse')
    if saml_response:
        user_data = IAMService.get_data_via_ws('response', saml_response, 'retUserFromIamResponse')
        if user_data:
            user = IAMService.store_update_user_data(user_data)
            if user:
                if user_has_required_permissions(user):
                    login(request, user, backend='blockchain_certificates.auth_backends.nafath_backend.NafathBackend')
                    return redirect('/index/')
                else:
                    return render(request, 'forbidden.html')
            else:
                return render(request, 'error_login.html')
        else:
            return HttpResponse("Invalid SAML response.", status=400)
    else:
        return HttpResponse("No SAML response provided.", status=400)

def user_has_required_permissions(user):
    # """Check if the user has the required permissions. Implement as needed."""
    # required_permission = 'required_permission'  # Replace with the actual required permission
    # return user.has_perm(required_permission)
    """
    High-security check: Allow login only if the user is authenticated,
    has a profile, and the profile has at least one valid role.
    """
    return (
        user.is_authenticated and
        hasattr(user, 'profile') and
        user.profile is not None and
        user.profile.roles.exists()
    )

def create_iam_logout_req(request):
    """Initiate IAM logout request and redirect to IAM logout page."""
    user_details = request.user.details
    data = IAMService.iam_logout(user_details)
    if data:
        logout(request)
        return HttpResponseRedirect(data)
    else:
        return HttpResponse("Error initiating IAM logout.", status=500)

