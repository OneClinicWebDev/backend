def has_role(request, role_name):
    return getattr(request, "role", None) == role_name


def is_admin(request):
    return request.role == "ADMIN"


def is_secretario(request):
    return request.role == "SECRETARIO"


def is_profissional(request):
    return request.role == "PROFISSIONAL"