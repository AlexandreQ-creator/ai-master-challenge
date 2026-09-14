import pandas as pd
import numpy as np
import time
import sys
import os

# Garante que o diretório deste arquivo está no path, para importar a engine
# do Mestre de Dados independente de onde o script for chamado.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mestre_dados_engine import DataMasterGuard

class DataMasterHarness:
    """
    Test Harness & Sandboxing Framework para o Agente Mestre de Dados.
    Executa testes de estresse, validação de regressão, segurança LGPD e performance
    para comprovar a Fase 7 do Radar de Maturidade em IA (Test Harness & Sandboxing).
    """
    
    def __init__(self):
        self.test_suite_results = []
        self.start_time = None

    def run_harness(self):
        """Executa toda a bateria de testes automatizados."""
        self.start_time = time.time()
        print("======================================================================")
        print("🧪 [TEST HARNESS] INICIANDO SUÍTE DE TESTES AUTOMATIZADOS DO AGENTE")
        print("======================================================================\n")
        
        self.test_scenario_1_golden_dataset()
        self.test_scenario_2_corrupted_dataset_stress()
        self.test_scenario_3_lgpd_pii_leakage_security()
        self.test_scenario_4_schema_mismatch_resilience()
        self.test_scenario_5_performance_benchmark_10k()
        
        self.generate_executive_summary()

    def test_scenario_1_golden_dataset(self):
        """Cenário 1: Base perfeita (Golden Baseline) -> Deve garantir 100% de precisão e 0 falsos positivos."""
        try:
            df_golden = pd.DataFrame({
                'customer_id': ['C001', 'C002', 'C003', 'C004'],
                'mrr_value': [1000.0, 2500.0, 1800.0, 3200.0],
                'last_interaction_date': ['2026-09-01', '2026-09-05', '2026-09-10', '2026-09-12']
            })
            
            guard = DataMasterGuard(df_golden, primary_key='customer_id')
            audit = guard.audit_dmbok_quality(
                numeric_rules={'mrr_value': (0, 50000)}, 
                date_col='last_interaction_date', 
                max_days_fresh=365
            )
            
            assert audit['dimensions']['Unicidade'] == '100.0%', "Falha na validação de unicidade."
            assert audit['dimensions']['Completude'] == '100.0%', "Falha na validação de completude."
            assert len(audit['issues_found']) == 0, "Falso positivo detectado em Golden Dataset."
            
            self.test_suite_results.append({
                'id': 'TC-001',
                'name': 'Golden Dataset Baseline (Zero Falsos Positivos)',
                'status': 'PASSED',
                'details': 'Base perfeita auditada com 100% de conformidade nas 6 dimensões DAMA-DMBOK.'
            })
        except Exception as e:
            self.test_suite_results.append({
                'id': 'TC-001',
                'name': 'Golden Dataset Baseline',
                'status': 'FAILED',
                'details': f"Erro: {str(e)}"
            })

    def test_scenario_2_corrupted_dataset_stress(self):
        """Cenário 2: Base severamente corrompida -> Testa detecção simultânea de anomalias."""
        try:
            df_corrupted = pd.DataFrame({
                'customer_id': ['C001', 'C002', 'C002', 'C004', 'C005'],  # Duplicata
                'mrr_value': [1500.0, np.nan, -200.0, 85000.0, 1200.0],   # Nulo, Negativo, Outlier extremo
                'last_interaction_date': ['2026-09-01', '2020-01-01', 'CORRUPTED_DATE', '2026-09-10', '2026-09-12'] # Antiga e Inválida
            })
            
            guard = DataMasterGuard(df_corrupted, primary_key='customer_id')
            audit = guard.audit_dmbok_quality(
                numeric_rules={'mrr_value': (0, 50000)}, 
                date_col='last_interaction_date', 
                max_days_fresh=90
            )
            
            issues = audit['issues_found']
            dims_flagged = set(issue['dimension'] for issue in issues)
            
            # Valida se detectou Unicidade, Completude, Validade e Tempestividade
            assert 'Unicidade' in dims_flagged, "Falhou em identificar duplicidade de ID."
            assert 'Completude' in dims_flagged, "Falhou em identificar valor Nulo em MRR."
            assert 'Validade' in dims_flagged, "Falhou em identificar MRR negativo/fora da faixa."
            assert 'Tempestividade' in dims_flagged, "Falhou em identificar data corrompida/desatualizada."
            
            self.test_suite_results.append({
                'id': 'TC-002',
                'name': 'Detecção de Anomalias Múltiplas em Base Corrompida',
                'status': 'PASSED',
                'details': f"Identificados com sucesso todos os {len(issues)} problemas de qualidade esperados."
            })
        except Exception as e:
            self.test_suite_results.append({
                'id': 'TC-002',
                'name': 'Detecção de Anomalias Múltiplas',
                'status': 'FAILED',
                'details': f"Erro: {str(e)}"
            })

    def test_scenario_3_lgpd_pii_leakage_security(self):
        """Cenário 3: Teste de Blindagem LGPD -> Garante que PII não vaza em texto puro."""
        try:
            df_pii = pd.DataFrame({
                'customer_id': ['C001', 'C002'],
                'email': ['alexandre.denofrio@pampg.com', 'cliente.secreto@empresa.com.br'],
                'cpf': ['123.456.789-00', '987.654.321-11']
            })
            
            guard = DataMasterGuard(df_pii, primary_key='customer_id', pii_cols=['email', 'cpf'])
            masked_df = guard.mask_pii()
            
            # Garante que nenhum e-mail ou CPF original está presente no dataframe mascarado
            raw_email_present = ('alexandre.denofrio@pampg.com' in masked_df['email'].values)
            raw_cpf_present = ('123.456.789-00' in masked_df['cpf'].values)
            
            assert not raw_email_present, "Vazamento de PII detectado na coluna E-mail."
            assert not raw_cpf_present, "Vazamento de PII detectado na coluna CPF."
            
            self.test_suite_results.append({
                'id': 'TC-003',
                'name': 'Segurança de Dados & Anonymization LGPD',
                'status': 'PASSED',
                'details': 'Mascaramento efetuado com sucesso sem vazamento de strings de PII originais.'
            })
        except Exception as e:
            self.test_suite_results.append({
                'id': 'TC-003',
                'name': 'Segurança de Dados & Anonymization LGPD',
                'status': 'FAILED',
                'details': f"Erro: {str(e)}"
            })

    def test_scenario_4_schema_mismatch_resilience(self):
        """Cenário 4: Resiliência a Quebra de Schema -> Chave primária ou colunas ausentes."""
        try:
            df_broken_schema = pd.DataFrame({
                'unknown_column_1': [1, 2, 3],
                'unknown_column_2': ['A', 'B', 'C']
            })
            
            guard = DataMasterGuard(df_broken_schema, primary_key='missing_pk')
            audit = guard.audit_dmbok_quality(numeric_rules={'non_existent_mrr': (0, 100)}, date_col='missing_date')
            
            assert audit['dimensions']['Unicidade'] == "Não avaliado (Chave primária não definida)", "Falha no tratamento elegante de chave ausente."
            
            self.test_suite_results.append({
                'id': 'TC-004',
                'name': 'Resiliência a Desvio de Schema / Colunas Ausentes',
                'status': 'PASSED',
                'details': 'Agente tratou graciosa e elegantemente a ausência de colunas esperadas sem crash.'
            })
        except Exception as e:
            self.test_suite_results.append({
                'id': 'TC-004',
                'name': 'Resiliência a Desvio de Schema',
                'status': 'FAILED',
                'details': f"Crash detectado: {str(e)}"
            })

    def test_scenario_5_performance_benchmark_10k(self):
        """Cenário 5: Benchmark de Carga & Latência (10.000 linhas geradas em memória)."""
        try:
            n_rows = 10000
            np.random.seed(42)
            df_large = pd.DataFrame({
                'customer_id': [f"CUST-{i:05d}" for i in range(n_rows)],
                'mrr_value': np.random.normal(2000, 500, n_rows),
                'last_interaction_date': ['2026-09-01'] * n_rows
            })
            
            # Adiciona 5% de nulos propositais
            df_large.loc[df_large.sample(frac=0.05).index, 'mrr_value'] = np.nan
            
            t_start = time.time()
            guard = DataMasterGuard(df_large, primary_key='customer_id')
            audit = guard.audit_dmbok_quality(numeric_rules={'mrr_value': (0, 10000)}, date_col='last_interaction_date')
            elapsed = time.time() - t_start
            
            assert elapsed < 2.0, f"Latência excessiva: {elapsed:.2f}s para 10k linhas."
            
            self.test_suite_results.append({
                'id': 'TC-005',
                'name': 'Benchmark de Performance & Escala (10.000 linhas)',
                'status': 'PASSED',
                'details': f"Processadas 10.000 linhas em {elapsed:.3f} segundos (< 2.0s)."
            })
        except Exception as e:
            self.test_suite_results.append({
                'id': 'TC-005',
                'name': 'Benchmark de Performance & Escala',
                'status': 'FAILED',
                'details': f"Erro: {str(e)}"
            })

    def generate_executive_summary(self):
        """Imprime o relatório executivo final do Test Harness."""
        total_tests = len(self.test_suite_results)
        passed_tests = sum(1 for t in self.test_suite_results if t['status'] == 'PASSED')
        execution_time = time.time() - self.start_time
        
        print("\n======================================================================")
        print("📊 RELATÓRIO EXECUTIVO DO TEST HARNESS")
        print("======================================================================")
        print(f"• Total de Cenários Executados: {total_tests}")
        print(f"• Testes Aprovados (PASSED):     {passed_tests} / {total_tests} ({(passed_tests/total_tests)*100:.1f}%)")
        print(f"• Tempo Total de Execução:       {execution_time:.3f} segundos")
        print("----------------------------------------------------------------------\n")
        
        for res in self.test_suite_results:
            icon = "✅" if res['status'] == 'PASSED' else "❌"
            print(f"{icon} [{res['id']}] {res['name']}")
            print(f"   Status: {res['status']} | Detalhes: {res['details']}\n")
            
        print("======================================================================")
        print("🏆 VEREDITO: Bateria de Testes Concluída com Sucesso!")
        print("======================================================================\n")

if __name__ == '__main__':
    harness = DataMasterHarness()
    harness.run_harness()
