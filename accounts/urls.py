from django.urls import path
from .views import (
    register_view,
    login_view,
    logout_view,
    forgot_password_view,
    reset_password_view,
    verify_otp_view,
    resend_otp_view,
)

urlpatterns = [
    path('signup/', register_view, name='register'),
    path('signin/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('verifyotp/', verify_otp_view, name='verify_otp'),
    path('verifyotp', verify_otp_view),
    path('resendotp/', resend_otp_view, name='resend_otp'),
    path('resendotp', resend_otp_view),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('resetpassword/', reset_password_view, name='reset_password'),
]
