from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, ProfileForm, RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:home')
    form = RegisterForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Регистрация прошла успешно. Теперь можно оформить заявку.')
        return redirect('repairs:create')
    return render(request, 'accounts/register.html', {'form': form})


class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def home(request):
    """Точка входа после логина: каждая роль попадает на свою стартовую страницу."""
    user = request.user
    if user.is_admin_role:
        return redirect('dashboard:requests')
    if user.is_master:
        return redirect('repairs:master_list')
    return redirect('repairs:my_list')


@login_required
def profile(request):
    form = ProfileForm(request.POST if request.method == 'POST' else None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Профиль сохранён.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {'form': form})
