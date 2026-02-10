#perfect one
import requests
import json
from django.conf import settings
from django.contrib.auth.models import User
from certificates.models import UserDetails  # Correctly reference the model from the certificates app
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class IAMService:
    @staticmethod
    def get_data_via_ws(data_name, data_value, path):
        url = f"{settings.KKU_IAM_WS_URL}/{path}"
        data = {
            "wsUsername": settings.KKU_SERVICES_USER,
            "wsPassword": settings.KKU_SERVICES_PASS,
            data_name: data_value,
        }
        try:
            response = requests.post(url, json=data)
            if response.headers['Content-Type'] == 'application/json':
                response_data = response.json()
                if response_data.get('success'):
                    return response_data['data']
                else:
                    logger.error("IAM WS response error: %s", response_data)
                    return None
            else:
                logger.error("Unexpected response type: %s", response.headers['Content-Type'])
                return None
        except requests.exceptions.RequestException as e:
            logger.error("Request exception during IAM WS request: %s", str(e))
            return None
        except ValueError:
            logger.error("Invalid JSON response")
            return None

    @staticmethod
    def store_update_user_data(data):
        
        user = IAMService.check_user_is_stored(data)
        if not user:
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        username=data['userid'],
                        email=f"iam.{data['userid']}@kku.edu.sa",
                        first_name=data.get('arabicFirstName', ''),
                        last_name=data.get('arabicFamilyName', ''),
                    )
                    UserDetails.objects.create(
                        user=user,
                        sessionIndex=data['sessionIndex'],
                        userid=data['userid'],
                        arabicName=data['arabicName'],
                        arabicFirstName=data['arabicFirstName'],
                        arabicFatherName=data['arabicFatherName'],
                        arabicGrandFatherName=data['arabicGrandFatherName'],
                        arabicFamilyName=data['arabicFamilyName'],
                        englishName=data['englishName'],
                        englishFirstName=data['englishFirstName'],
                        englishFatherName=data['englishFatherName'],
                        englishGrandFatherName=data['englishGrandFatherName'],
                        englishFamilyName=data['englishFamilyName'],
                        nationalityCode=data['nationalityCode'],
                        arabicNationality=data['arabicNationality'],
                        nationality=data['nationality'],
                        dob=data['dob'],
                        dobHijri=data['dobHijri'],
                        gender=data['gender'],
                        lang=data['lang'],
                        preferredLang=data['preferredLang'],
                        idVersionNo=data['idVersionNo'],
                        idExpiryDateHijri=data['idExpiryDateHijri'],
                        idExpiryDateGregorian=data['idExpiryDateGregorian'],
                        iqamaExpiryDateHijri=data['iqamaExpiryDateHijri'],
                        iqamaExpiryDateGregorian=data['iqamaExpiryDateGregorian'],
                        cardIssueDateHijri=data['cardIssueDateHijri'],
                        cardIssueDateGregorian=data['cardIssueDateGregorian'],
                        issueLocationAr=data['issueLocationAr'],
                        issueLocationEn=data['issueLocationEn'],
                        iam_login=True,
                    )
                    
                    # Update UserProfile phone number if available
                    phone = data.get('mobileNo', '')
                    if phone:
                        try:
                            profile = user.profile
                            profile.phone = phone
                            profile.save()
                        except Exception as e:
                            logger.error("Error setting phone in new profile: %s", str(e))
                    
            except Exception as ex:
                logger.error("Error storing data from IAM: %s", str(ex))
                return None
        else:
            try:
                with transaction.atomic():
                    user.username = data['userid']
                    # Only set email if user doesn't have one already (preserve manual changes)
                    if not user.email:
                        user.email = f"iam.{data['userid']}@kku.edu.sa"
                    user.first_name = data.get('arabicFirstName', '')
                    user.last_name = data.get('arabicFamilyName', '')
                    user.save()

                    user.details.sessionIndex = data['sessionIndex']
                    user.details.userid = data['userid']
                    user.details.arabicName = data['arabicName']
                    user.details.arabicFirstName = data['arabicFirstName']
                    user.details.arabicFatherName = data['arabicFatherName']
                    user.details.arabicGrandFatherName = data['arabicGrandFatherName']
                    user.details.arabicFamilyName = data['arabicFamilyName']
                    user.details.englishName = data['englishName']
                    user.details.englishFirstName = data['englishFirstName']
                    user.details.englishFatherName = data['englishFatherName']
                    user.details.englishGrandFatherName = data['englishGrandFatherName']
                    user.details.englishFamilyName = data['englishFamilyName']
                    user.details.nationalityCode = data['nationalityCode']
                    user.details.arabicNationality = data['arabicNationality']
                    user.details.nationality = data['nationality']
                    user.details.dob = data['dob']
                    user.details.dobHijri = data['dobHijri']
                    user.details.gender = data['gender']
                    user.details.lang = data['lang']
                    user.details.preferredLang = data['preferredLang']
                    user.details.idVersionNo = data['idVersionNo']
                    user.details.idExpiryDateHijri = data['idExpiryDateHijri']
                    user.details.idExpiryDateGregorian = data['idExpiryDateGregorian']
                    user.details.iqamaExpiryDateHijri = data['iqamaExpiryDateHijri']
                    user.details.iqamaExpiryDateGregorian = data['iqamaExpiryDateGregorian']
                    user.details.cardIssueDateHijri = data['cardIssueDateHijri']
                    user.details.cardIssueDateGregorian = data['cardIssueDateGregorian']
                    user.details.issueLocationAr = data['issueLocationAr']
                    user.details.issueLocationEn = data['issueLocationEn']
                    user.details.iam_login = True
                    user.details.save()
                    
                    # Update UserProfile phone number if available
                    phone = data.get('mobileNo', '')
                    if phone:
                        try:
                            profile = user.profile
                            profile.phone = phone
                            profile.save()
                        except Exception as e:
                            logger.error("Error updating phone in profile: %s", str(e))
                    
            except Exception as ex:
                logger.error("Error updating data from IAM: %s", str(ex))
                return None

        return user

    @staticmethod
    def check_user_is_stored(data):
        return User.objects.filter(details__userid=data['userid']).first()

    @staticmethod
    def iam_logout(user_details):
        data = {
            "wsUsername": settings.KKU_SERVICES_USER,
            "wsPassword": settings.KKU_SERVICES_PASS,
            "userId": user_details.userid,
            "sessionIndex": user_details.sessionIndex,
        }
        try:
            response = requests.post(f"{settings.KKU_IAM_WS_URL}/createIamLogoutReq", json=data)
            response_data = response.json()
            if response_data.get('success'):
                return response_data['data']
            else:
                logger.error("IAM WS logout response error: %s", response_data)
                return None
        except requests.exceptions.RequestException as e:
            logger.error("Request exception during IAM WS logout: %s", str(e))
            return None
        except ValueError:
            logger.error("Invalid JSON response during IAM WS logout")
            return None


