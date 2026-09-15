# Dados de audiência

`audiences.csv` é um snapshot da base Cadu. Os campos de taxonomia explicam o que o item representa; `data_quality_status`, origem, observação e validade determinam quanto peso ele pode receber. `measurements` contém medições com suas próprias fontes e períodos.

Use `available_channels` como vínculo principal de ativação. Quando vazio, plataforma/fonte pode orientar uma validação, mas não comprova disponibilidade. `verification_candidate` significa apenas que os campos mínimos estão completos; a aprovação humana e a atualização da base continuam obrigatórias. Não exponha dados pessoais, preço de custo, preço de venda ou JSON cru.
