def has_role(user, role_name, clinica):
    from core.models import Colaborador

    return Colaborador.objects.filter(
        usuario=user,
        clinica=clinica,
        role__nome=role_name,
        ativo=True
    ).exists()