import json
import datetime
import os
from core.database import supabase

TABELAS_CRITICAS = [
    "usuarios", 
    "tco_bens", 
    "tco_logs", 
    "audit_log", 
    "aceites_compliance", 
    "configuracoes_sistema"
]

def executar_backup_frio_local():
    if not supabase:
        print("❌ Conexão com Supabase indisponível.")
        return

    data_hoje = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_backup = os.path.join(os.path.expanduser("~"), ".siop_backups_offline")
    os.makedirs(pasta_backup, exist_ok=True)

    backup_dados = {}
    for tabela in TABELAS_CRITICAS:
        try:
            res = supabase.table(tabela).select("*").execute()
            backup_dados[tabela] = res.data or []
        except Exception as e:
            backup_dados[tabela] = f"Erro: {e}"

    caminho_arquivo = os.path.join(pasta_backup, f"siop_dump_completo_{data_hoje}.json")
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(backup_dados, f, ensure_ascii=False, indent=4)

    print(f"✅ Backup local de emergência salvo com sucesso em:\n{caminho_arquivo}")

if __name__ == "__main__":
    executar_backup_frio_local()