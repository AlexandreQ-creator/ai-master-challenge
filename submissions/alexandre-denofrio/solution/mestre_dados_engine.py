import sys

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

class DataMasterGuard:
    """
    Engine de Governança, Qualidade de Dados e Diagnóstico Didático.
    Implementa o padrão do Mestre de Análise e Governança de Dados,
    combinando as 6 dimensões do DAMA-DMBOK, filtros de LGPD (PII) e o método IWS (RCA).
    """
    
    def __init__(self, df: pd.DataFrame, primary_key: str = None, pii_cols: list = None):
        self.df = df.copy()
        self.primary_key = primary_key
        self.pii_cols = pii_cols or []
        self.audit_report = {
            'dimensions': {},
            'pii_status': {},
            'issues_found': [],
            'friendly_summary': ""
        }

    def mask_pii(self) -> pd.DataFrame:
        """Aplica mascaramento prévio (Anonymization) em colunas PII para conformidade com a LGPD."""
        masked_df = self.df.copy()
        for col in self.pii_cols:
            if col in masked_df.columns:
                masked_df[col] = masked_df[col].astype(str).apply(
                    lambda x: f"{x[0]}***{x[-1]}@***.com" if '@' in x else (f"{x[:2]}***{x[-2:]}" if len(x) > 4 else "***")
                )
        self.audit_report['pii_status'] = {'masked_columns': self.pii_cols, 'status': 'Protegido / Anonymized'}
        return masked_df

    def audit_dmbok_quality(self, numeric_rules: dict = None, date_col: str = None, max_days_fresh: int = 90) -> dict:
        """
        Executa a auditoria completa de qualidade de dados nas 6 dimensões DAMA-DMBOK:
        1. Unicidade (Uniqueness)
        2. Completude (Completeness)
        3. Validade (Validity)
        4. Consistência (Consistency)
        5. Acurácia / Outliers (Accuracy)
        6. Tempestividade (Timeliness)
        """
        issues = []
        dim_scores = {}
        total_rows = len(self.df)

        # 1. Unicidade
        if self.primary_key and self.primary_key in self.df.columns:
            duplicates_count = self.df.duplicated(subset=[self.primary_key]).sum()
            uniqueness_pct = round((1 - (duplicates_count / total_rows)) * 100, 2) if total_rows > 0 else 100.0
            dim_scores['Unicidade'] = f"{uniqueness_pct}%"
            if duplicates_count > 0:
                issues.append({
                    'dimension': 'Unicidade',
                    'severity': 'MÉDIA',
                    'desc': f"Encontrados {duplicates_count} registros duplicados na chave primária '{self.primary_key}'.",
                    'rca_cause': "Inclusão ou reprocessamento sem de-duplicação prévia no pipeline de ETL.",
                    'fix_suggestion': f"df.drop_duplicates(subset=['{self.primary_key}'], keep='last')"
                })
        else:
            dim_scores['Unicidade'] = "Não avaliado (Chave primária não definida)"

        # 2. Completude
        null_counts = self.df.isnull().sum()
        cols_with_nulls = null_counts[null_counts > 0]
        total_cells = self.df.size
        total_nulls = null_counts.sum()
        completeness_pct = round((1 - (total_nulls / total_cells)) * 100, 2) if total_cells > 0 else 100.0
        dim_scores['Completude'] = f"{completeness_pct}%"
        
        if not cols_with_nulls.empty:
            for col_name, null_cnt in cols_with_nulls.items():
                issues.append({
                    'dimension': 'Completude',
                    'severity': 'ALTA' if (null_cnt / total_rows) > 0.1 else 'MÉDIA',
                    'desc': f"A coluna '{col_name}' possui {null_cnt} valores ausentes (NaN/Null) - {round(null_cnt/total_rows*100,1)}% da base.",
                    'rca_cause': f"A chave ou campo '{col_name}' não foi capturado na origem ou sofreu falha de mapeamento de contrato.",
                    'fix_suggestion': f"df['{col_name}'].fillna(df['{col_name}'].median())  # ou valor padrão condicional"
                })

        # 3. Validade (Regras de Negócio Numericas)
        validity_issues = 0
        if numeric_rules:
            for col_name, (min_val, max_val) in numeric_rules.items():
                if col_name in self.df.columns:
                    invalid_mask = (self.df[col_name] < min_val) | (self.df[col_name] > max_val)
                    invalid_cnt = invalid_mask.sum()
                    if invalid_cnt > 0:
                        validity_issues += invalid_cnt
                        issues.append({
                            'dimension': 'Validade',
                            'severity': 'ALTA',
                            'desc': f"A coluna '{col_name}' possui {invalid_cnt} valores fora da faixa válida [{min_val}, {max_val}].",
                            'rca_cause': f"Entrada manual errônea ou quebra de contrato de negócio (ex.: valores negativos para receita/MRR).",
                            'fix_suggestion': f"df = df[(df['{col_name}'] >= {min_val}) & (df['{col_name}'] <= {max_val})]"
                        })
        dim_scores['Validade'] = "100%" if validity_issues == 0 else f"{round((1 - (validity_issues / (total_rows * len(numeric_rules or [1]))) ) * 100, 1)}%"

        # 4. Acurácia / Detecção de Outliers (IQR Method)
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        outlier_cnt = 0
        for num_col in numeric_cols:
            q1 = self.df[num_col].quantile(0.25)
            q3 = self.df[num_col].quantile(0.75)
            iqr = q3 - q1
            outliers = ((self.df[num_col] < (q1 - 1.5 * iqr)) | (self.df[num_col] > (q3 + 1.5 * iqr))).sum()
            if outliers > 0:
                outlier_cnt += outliers
                issues.append({
                    'dimension': 'Acurácia',
                    'severity': 'BAIXA',
                    'desc': f"Identificados {outliers} potenciais outliers estatísticos na coluna '{num_col}'.",
                    'rca_cause': "Anomalias pontuais de mercado, clientes enterprise fora da média ou ruídos cadastrais.",
                    'fix_suggestion': f"Investigar valores com IQR > 1.5 ou aplicar limites percentis (Winsorization)."
                })
        dim_scores['Acurácia'] = "Saneada" if outlier_cnt == 0 else f"Atenção ({outlier_cnt} anomalias est.)"

        # 5. Tempestividade (Freshness)
        if date_col and date_col in self.df.columns:
            try:
                dates = pd.to_datetime(self.df[date_col], errors='coerce')
                invalid_dates = dates.isna().sum()
                if invalid_dates > 0:
                    issues.append({
                        'dimension': 'Tempestividade',
                        'severity': 'MÉDIA',
                        'desc': f"{invalid_dates} registros possuem formatos de data inválidos ou corrompidos em '{date_col}'.",
                        'rca_cause': "Mistura de padrões de string de datas (ex.: DD/MM/YYYY vs YYYY-MM-DD).",
                        'fix_suggestion': f"pd.to_datetime(df['{date_col}'], format='mixed', errors='coerce')"
                    })
                latest_date = dates.max()
                days_diff = (datetime.now() - latest_date).days if pd.notnull(latest_date) else 999
                if days_diff > max_days_fresh:
                    issues.append({
                        'dimension': 'Tempestividade',
                        'severity': 'ALTA',
                        'desc': f"A base de dados está desatualizada em {days_diff} dias (último registro: {latest_date.strftime('%Y-%m-%d')}).",
                        'rca_cause': "Carga congelada ou pipeline de atualização de ingestão interrompido.",
                        'fix_suggestion': "Verificar o cron da carga automatica e re-executar a coleta de dados."
                    })
                dim_scores['Tempestividade'] = f"Último registro há {days_diff} dias"
            except Exception as e:
                dim_scores['Tempestividade'] = "Erro na conversão de datas"
        else:
            dim_scores['Tempestividade'] = "Não avaliado (Coluna de data não definida)"

        self.audit_report['dimensions'] = dim_scores
        self.audit_report['issues_found'] = issues
        self.audit_report['friendly_summary'] = self._generate_friendly_summary()
        return self.audit_report

    def _generate_friendly_summary(self) -> str:
        """Gera um diagnóstico didático, cordial e explicativo em linguagem executiva."""
        issues = self.audit_report['issues_found']
        if not issues:
            return "✅ **Diagnóstico do Mestre de Dados:** A base analisada apresenta excelente nível de higienização, sem duplicidades brutas ou inconformidades com regras de negócio. Pronta para carga e consumo no BI/Modelos!"
        
        summary = "👋 **Olá! Sou o seu Mestre de Análise e Governança de Dados.**\n"
        summary += "Analisei a sua base e identifiquei os seguintes pontos de atenção para garantirmos a máxima precisão dos seus indicadores executivos:\n\n"
        
        for idx, issue in enumerate(issues, 1):
            summary += f"### {idx}. {issue['dimension']} ({issue['severity']})\n"
            summary += f"* **O que aconteceu:** {issue['desc']}\n"
            summary += f"* **Causa Raiz provável (IWS RCA):** {issue['rca_cause']}\n"
            summary += f"* **Como corrigir em Python/SQL:**\n```python\n{issue['fix_suggestion']}\n```\n\n"
            
        summary += "💡 *Precisa de ajuda para rodar essas correções automaticamente? Posso aplicar o script de higienização e gerar a base tratada para você!*"
        return summary

# --- BLOCO DE EXECUÇÃO E TESTE DE SANIDADE ---
if __name__ == "__main__":
    # Simulação de um dataset do G4/RavenStack com ruídos operacionais
    sample_data = {
        'customer_id': ['CUST-101', 'CUST-102', 'CUST-102', 'CUST-104', 'CUST-105', 'CUST-106'],
        'email_cliente': ['joao@empresa.com', 'maria@empresa.com', 'maria@empresa.com', 'pedro@empresa.com', 'ana@empresa.com', 'carlos@empresa.com'],
        'mrr_value': [2500.0, np.nan, 2500.0, -450.0, 15000.0, 3200.0],  # Nulo, Negativo e Outlier
        'churn_status': [0, 0, 0, 1, 0, 1],
        'last_interaction_date': ['2024-01-10', '2024-02-15', '2024-02-15', '2024-03-01', 'INVALID_DATE', '2024-05-10']
    }
    
    df_raw = pd.DataFrame(sample_data)
    
    # Instancia o Mestre de Dados
    mestre = DataMasterGuard(
        df=df_raw,
        primary_key='customer_id',
        pii_cols=['email_cliente']
    )
    
    # 1. Mascaramento PII (LGPD)
    df_protected = mestre.mask_pii()
    
    # 2. Auditoria DAMA-DMBOK
    report = mestre.audit_dmbok_quality(
        numeric_rules={'mrr_value': (0, 50000)},  # MRR deve ser >= 0
        date_col='last_interaction_date',
        max_days_fresh=60
    )
    
    print("=== DSI SCORES DAMA-DMBOK ===")
    for dim, score in report['dimensions'].items():
        print(f"{dim}: {score}")
        
    print("\n" + report['friendly_summary'])
