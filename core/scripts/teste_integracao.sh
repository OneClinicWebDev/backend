#!/usr/bin/env bash
# Teste de integração da API do OneClinic contra um servidor LOCAL em execução.
# Uso (Git Bash, com o servidor rodando e o venv ativo):
#   bash scripts/teste_integracao.sh                 # fase 1: login, clínica ativa, agenda e negativos
#   CLIENTE_USUARIO_ID=<uuid> bash scripts/teste_integracao.sh   # fase 2: também cria serviço, cliente e agendamentos
#
# Pede CPF e senha no terminal (a senha não aparece nem fica salva).
# Variáveis opcionais: BASE (padrão http://127.0.0.1:8000), CLINICA_ID (padrão: 1º vínculo).
# Nunca aponte BASE para produção: a fase 2 grava dados. A fase 2 exige um usuário ADMIN
# e deixa o cliente de teste cadastrado (reaproveitado nas próximas execuções).

export PYTHONIOENCODING=utf-8
BASE="${BASE:-http://127.0.0.1:8000}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
PASS=0
FAIL=0

# Extrai um valor de um JSON recebido na entrada. Ex.: jget vinculos 0 clinica_id
jget() {
python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k in sys.argv[1:]:
        d = d[int(k)] if isinstance(d, list) else d[k]
    print(d)
except (KeyError, IndexError, TypeError, ValueError):
    print('')
" "$@"
}

# call MÉTODO CAMINHO [argumentos do curl...]  ->  define CODE e BODY
call() {
  local method="$1" path="$2"
  shift 2
  CODE=$(curl -s -o "$TMP" -w "%{http_code}" -X "$method" "$BASE$path" "$@")
  BODY=$(cat "$TMP")
}

# check "descrição" código_esperado
check() {
  if [ "$CODE" = "$2" ]; then
    echo "  OK      $1 (HTTP $CODE)"
    PASS=$((PASS + 1))
  else
    echo "  FALHOU  $1: esperado $2, recebido $CODE"
    echo "          corpo: ${BODY:0:300}"
    FAIL=$((FAIL + 1))
  fi
}

JSON=(-H "Content-Type: application/json")

echo "== Servidor =="
call GET /api/agendamentos/
check "sem token a agenda exige autenticação" 401

echo "== Login =="
read -r -p "CPF (somente dígitos): " CPF
read -r -s -p "Senha: " SENHA
echo

call POST /api/auth/login/ "${JSON[@]}" -d "{\"cpf\":\"$CPF\",\"password\":\"$SENHA\"}"
check "login com CPF e senha" 200
if [ "$CODE" != "200" ]; then
  echo "Sem login não há como continuar."
  exit 1
fi
LOGIN="$BODY"
ACCESS=$(echo "$LOGIN" | jget access)
REFRESH=$(echo "$LOGIN" | jget refresh)
USUARIO_ID=$(echo "$LOGIN" | jget usuario id)
QTD_VINCULOS=$(echo "$LOGIN" | python -c "import sys,json; print(len(json.load(sys.stdin)['vinculos']))")
if [ "$QTD_VINCULOS" = "0" ]; then
  echo "  Este usuário não tem vínculo ativo com nenhuma clínica ativa, então não há clínica para testar."
  echo "  (É o esperado para um superusuário do Django, que não é ADMIN de clínica.)"
  echo "  Use o CPF de um usuário com vínculo de colaborador."
  exit 1
fi
CLINICA="${CLINICA_ID:-$(echo "$LOGIN" | jget vinculos 0 clinica_id)}"
echo "  vínculos disponíveis:"
echo "$LOGIN" | python -c "
import sys, json
for v in json.load(sys.stdin)['vinculos']:
    print('   -', v['clinica_id'], v['clinica_nome'], v['role'])
"
echo "  clínica usada nos testes: $CLINICA"

AUTH=(-H "Authorization: Bearer $ACCESS")
CLI=(-H "X-Clinica-ID: $CLINICA")

call POST /api/auth/login/ "${JSON[@]}" -H "Authorization: Bearer token-vencido" \
  -d "{\"cpf\":\"$CPF\",\"password\":\"$SENHA\"}"
check "login ignora um token vencido no cabeçalho" 200

call POST /api/auth/login/ "${JSON[@]}" -d "{\"cpf\":\"$CPF\",\"password\":\"senha-errada-123\"}"
check "login com senha errada é recusado" 400

echo "== Sessão e clínica ativa =="
call GET /api/auth/me/ "${AUTH[@]}"
check "me com token devolve usuário e vínculos" 200
call GET /api/auth/me/
check "me sem token" 401

call GET /api/agendamentos/ "${AUTH[@]}" "${CLI[@]}"
check "agenda da clínica ativa" 200
echo "$BODY" | python -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list), 'a agenda deveria ser uma lista'; print('  itens na agenda:', len(d))"

call GET /api/agendamentos/ "${AUTH[@]}"
check "sem X-Clinica-ID" 403
call GET /api/agendamentos/ "${AUTH[@]}" -H "X-Clinica-ID: 00000000-0000-0000-0000-000000000000"
check "clínica sem vínculo" 403
call GET /api/agendamentos/ "${AUTH[@]}" -H "X-Clinica-ID: isto-nao-e-um-uuid"
check "X-Clinica-ID malformado" 403
call GET /api/agendamentos/ -H "X-Clinica-ID: $CLINICA"
check "clínica informada, mas sem token" 401

echo "== Filtros da agenda =="
call GET "/api/agendamentos/?data_inicio=2026-01-01&data_fim=2026-12-31" "${AUTH[@]}" "${CLI[@]}"
check "filtro por período (datas)" 200
call GET "/api/agendamentos/?status=CONFIRMADO" "${AUTH[@]}" "${CLI[@]}"
check "filtro por status" 200
call GET "/api/agendamentos/?data_inicio=ontem" "${AUTH[@]}" "${CLI[@]}"
check "data inválida é recusada" 400
call GET "/api/agendamentos/?profissional=abc" "${AUTH[@]}" "${CLI[@]}"
check "UUID inválido é recusado" 400
call GET "/api/agendamentos/?status=FALTA" "${AUTH[@]}" "${CLI[@]}"
check "FALTA não é status de agendamento" 400

SERVICO_ID=""
AG1=""
AG2=""

# exigir "descrição" código: registra o resultado e devolve erro se o código não for o esperado
exigir() {
  check "$1" "$2"
  [ "$CODE" = "$2" ]
}

fase2() {
  # Somente ASCII nos corpos enviados pelo curl: no Windows, acentos em argumentos
  # chegam ao servidor em outra codificação e a API recusa o JSON.
  call POST /api/servicos/ "${AUTH[@]}" "${CLI[@]}" "${JSON[@]}" \
    -d '{"nome":"Teste de integracao","duracao_padrao_minutos":60}'
  exigir "criar serviço" 201 || return 1
  SERVICO_ID=$(echo "$BODY" | jget id)

  call POST /api/clientes/ "${AUTH[@]}" "${CLI[@]}" "${JSON[@]}" \
    -d "{\"usuario\":\"$CLIENTE_USUARIO_ID\",\"telefone\":\"(47) 99999-0000\"}"
  if [ "$CODE" = "201" ]; then
    check "criar cliente" 201
    CLIENTE_ID=$(echo "$BODY" | jget id)
  else
    echo "  cliente não criado (HTTP $CODE); procurando um cadastro ativo existente"
    call GET /api/clientes/ "${AUTH[@]}" "${CLI[@]}"
    exigir "listar clientes" 200 || return 1
    CLIENTE_ID=$(echo "$BODY" | python -c "
import sys, json
uid = sys.argv[1]
print(next((c['id'] for c in json.load(sys.stdin)
            if c['usuario'] == uid and c['status_cadastro'] == 'ATIVO'), ''))
" "$CLIENTE_USUARIO_ID")
    if [ -z "$CLIENTE_ID" ]; then
      echo "  Não há cliente ATIVO para esse usuário nesta clínica. Use outro CLIENTE_USUARIO_ID."
      return 1
    fi
  fi

  call GET /api/colaboradores/ "${AUTH[@]}" "${CLI[@]}"
  exigir "listar colaboradores (ADMIN)" 200 || return 1
  PROFISSIONAL_ID=$(echo "$BODY" | python -c "
import sys, json
uid = sys.argv[1]
print(next((c['id'] for c in json.load(sys.stdin) if c['usuario'] == uid), ''))
" "$USUARIO_ID")
  if [ -z "$PROFISSIONAL_ID" ]; then
    echo "  O usuário logado não possui vínculo de colaborador nesta clínica."
    return 1
  fi

  # Data de teste: daqui a 30 dias, fuso -03:00 (São Paulo, sem horário de verão).
  DIA=$(python -c "from datetime import date, timedelta; print(date.today() + timedelta(days=30))")
  mk() { echo "{\"cliente\":\"$CLIENTE_ID\",\"profissional\":\"$PROFISSIONAL_ID\",\"servico\":$SERVICO_ID,\"data_hora_inicio\":\"${DIA}T$1:00-03:00\",\"data_hora_fim\":\"${DIA}T$2:00-03:00\"}"; }

  call POST /api/agendamentos/ "${AUTH[@]}" "${CLI[@]}" "${JSON[@]}" -d "$(mk 10:00 11:00)"
  exigir "criar agendamento 10:00-11:00 (nasce CONFIRMADO)" 201 || return 1
  AG1=$(echo "$BODY" | jget id)
  echo "$BODY" | python -c "import sys,json; d=json.load(sys.stdin); print('  status:', d['status'], '| resultado:', d['resultado'])"

  call POST /api/agendamentos/ "${AUTH[@]}" "${CLI[@]}" "${JSON[@]}" -d "$(mk 10:30 11:30)"
  check "horário sobreposto é recusado" 409

  call POST /api/agendamentos/ "${AUTH[@]}" "${CLI[@]}" "${JSON[@]}" -d "$(mk 11:00 12:00)"
  exigir "horário adjacente 11:00-12:00 é permitido" 201 || return 1
  AG2=$(echo "$BODY" | jget id)

  call GET "/api/agendamentos/?data_inicio=$DIA&data_fim=$DIA" "${AUTH[@]}" "${CLI[@]}"
  exigir "filtro pelo dia dos agendamentos" 200 || return 1
  if echo "$BODY" | python -c "
import sys, json
d = json.load(sys.stdin)
print('  itens no dia:', len(d))
print('  campos:', ', '.join(sorted(d[0].keys())) if d else '(nenhum)')
sys.exit(0 if len(d) == 2 else 1)
"; then
    PASS=$((PASS + 1))
  else
    echo "  FALHOU  esperados exatamente 2 agendamentos no dia"
    FAIL=$((FAIL + 1))
  fi
}

limpar_fase2() {
  echo "== Limpeza (cancela os agendamentos e desativa o serviço criados) =="
  for ag in "$AG1" "$AG2"; do
    if [ -n "$ag" ]; then
      call POST "/api/agendamentos/$ag/cancelar/" "${AUTH[@]}" "${CLI[@]}" "${JSON[@]}" -d '{"motivo":"Teste de integracao"}'
      check "cancelar agendamento $ag" 200
    fi
  done
  if [ -n "$SERVICO_ID" ]; then
    call DELETE "/api/servicos/$SERVICO_ID/" "${AUTH[@]}" "${CLI[@]}"
    check "desativar serviço de teste" 204
  fi
}

if [ -z "$CLIENTE_USUARIO_ID" ]; then
  echo
  echo "Fase 2 (agendamentos) ignorada: defina CLIENTE_USUARIO_ID para executá-la."
else
  echo "== Fase 2: cenário de agendamento (grava no banco apontado pelo servidor) =="
  fase2 || echo "  Fase 2 interrompida por uma falha acima."
  limpar_fase2
fi

echo "== Ciclo de tokens (consome o refresh deste login) =="
call POST /api/token/refresh/ "${JSON[@]}" -d "{\"refresh\":\"$REFRESH\"}"
check "refresh devolve novo access e novo refresh" 200
NOVO_REFRESH=$(echo "$BODY" | jget refresh)
NOVO_ACCESS=$(echo "$BODY" | jget access)

call POST /api/token/refresh/ "${JSON[@]}" -d "{\"refresh\":\"$REFRESH\"}"
check "refresh antigo foi invalidado pela rotação" 401

call POST /api/auth/logout/ -H "Authorization: Bearer $NOVO_ACCESS" "${JSON[@]}" -d "{\"refresh\":\"$NOVO_REFRESH\"}"
check "logout invalida o refresh" 205

call POST /api/token/refresh/ "${JSON[@]}" -d "{\"refresh\":\"$NOVO_REFRESH\"}"
check "refresh após logout é recusado" 401

echo
echo "Resumo: $PASS ok, $FAIL falha(s)."
[ "$FAIL" -eq 0 ]