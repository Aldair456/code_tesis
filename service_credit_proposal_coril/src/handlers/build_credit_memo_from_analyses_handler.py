"""
Lambda auxiliar: recibe parallel_results (array) o evento combinado y arma el body
listo para create_credit_proposal_coril. Solo orquesta; la lógica está en CreditMemoBuilderService.
"""
import logging
from typing import Dict, Any

from common.exceptions.exceptions import BadRequestError
from services.service_credit_proposal_coril.src.config.dependencies import get_credit_memo_builder_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_memo_builder_service = get_credit_memo_builder_service()

import json
from typing import Dict, List, Any

def limpiar_duplicados_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Elimina duplicados de cuentas en el JSON manteniendo la que tenga más información.
    
    Args:
        data: Diccionario con el JSON completo
        
    Returns:
        Diccionario con el JSON limpio sin duplicados
    """
    
    def calcular_score(item: Dict[str, Any]) -> int:
        """Calcula score según información disponible"""
        score = 0
        if item.get('ltm_amount') and item['ltm_amount'] != '-':
            score += 3
        if item.get('ltm_percentage') and item['ltm_percentage'] != '-':
            score += 2
        if item.get('last_period_amount') and item['last_period_amount'] != '-':
            score += 1
        return score
    
    def eliminar_duplicados(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Elimina duplicados por label, manteniendo el que tenga más info"""
        if not items:
            return items
        
        grupos = {}
        for item in items:
            label = item.get('label', '')
            if label not in grupos:
                grupos[label] = []
            grupos[label].append(item)
        
        resultado = []
        for grupo_items in grupos.values():
            if len(grupo_items) == 1:
                resultado.append(grupo_items[0])
            else:
                mejor = max(grupo_items, key=calcular_score)
                resultado.append(mejor)
        
        return resultado
    
    # Crear copia del JSON
    data_limpio = json.loads(json.dumps(data))
    
    # Limpiar cada sección
    if 'proposal_data' in data_limpio:
        pd = data_limpio['proposal_data']
        
        # Limpiar financial_results
        if 'financial_results' in pd and 'financial_results_list' in pd['financial_results']:
            pd['financial_results']['financial_results_list'] = eliminar_duplicados(
                pd['financial_results']['financial_results_list']
            )
        
        # Limpiar balance_general
        if 'balance_general' in pd and 'balance_sheet_list' in pd['balance_general']:
            pd['balance_general']['balance_sheet_list'] = eliminar_duplicados(
                pd['balance_general']['balance_sheet_list']
            )
        
        # Limpiar cash_flow
        if 'cash_flow' in pd and 'cash_flow_list' in pd['cash_flow']:
            # Filtrar fila total 'Flujo de Caja' que el usuario no quiere mostrar
            original_cf_list = pd['cash_flow']['cash_flow_list']
            filtered_cf_list = [item for item in original_cf_list if item.get('label', '').upper() != 'FLUJO DE CAJA']
            pd['cash_flow']['cash_flow_list'] = eliminar_duplicados(filtered_cf_list)
    
    return data_limpio
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Input (uno de los dos):
    - parallel_results (array) + business_id: output del estado Parallel.
    - business_id + producto_demanda_mercado, sector_economico, ... en la raíz: output de CombineResults.

    Campos opcionales: total_amount, currency, credit_type, term, guarantee, report_title,
    credit_memo_id, user_id, deal_id, proposal_number.

    Output: body_for_create para pasarlo al lambda create_credit_proposal_coril.
    """
    request_id = getattr(context, "aws_request_id", "unknown") if context else "unknown"
    logger.info("Build credit memo from analyses - Request ID: %s", request_id)

    try:
        body_for_create_2 = credit_memo_builder_service.build_body_for_create(event)
        body_for_create = limpiar_duplicados_json(body_for_create_2)
        logger.info("Body para create_credit_proposal_coril generado exitosamente - Request ID: %s", request_id)
        return body_for_create
    except BadRequestError:
        raise
    except Exception as err:
        logger.error("Error en build_credit_memo_from_analyses: %s - Request ID: %s", err, request_id, exc_info=True)
        raise


   

class Context:
    def __init__(self):
        self.aws_request_id = "test-request-id"
event = {
  "parallel_results": [
    {
      "business_id": "43e9f078-e9c3-4150-8689-0758ab06512e",
      "analysis": {
        "sector_economico": {
          "contenido": "**Sector Energy – Oil, Gas & Consumable Fuels en Perú**\n\nEl sector hidrocarburos en Perú atraviesa un periodo de desafíos estructurales y coyunturales que condicionan el desempeño de las empresas vinculadas a la exploración, producción, refinación y comercialización de petróleo, gas y combustibles. La producción nacional de petróleo crudo se mantiene en niveles históricamente bajos, con una extracción que en 2024 promedió alrededor de 40 mil barriles diarios, cifra insuficiente para cubrir la demanda interna, lo que obliga al país a importar volúmenes significativos de crudo y productos derivados. Esta dependencia de las importaciones expone al mercado local a la volatilidad de los precios internacionales del petróleo, que durante 2024 fluctuaron en un rango de USD 70 a USD 85 por barril (Brent), y que para 2025 se proyectan con presión a la baja ante expectativas de menor crecimiento global y mayor oferta de la OPEP+.\n\nEn cuanto al gas natural, el proyecto Camisea continúa siendo el pilar de la producción nacional, abasteciendo tanto el consumo doméstico como la exportación de gas natural licuado (GNL). Sin embargo, la maduración de los yacimientos y la falta de nuevos contratos de exploración de gran escala generan incertidumbre sobre la sostenibilidad de la oferta a mediano plazo. El Ministerio de Energía y Minas ha impulsado durante 2024 y 2025 iniciativas para reactivar la inversión en exploración, incluyendo la simplificación de procesos de licenciamiento y la promoción de nuevas rondas de licitación de lotes petroleros, aunque los resultados concretos aún son limitados.\n\nLa demanda interna de combustibles líquidos mostró un crecimiento moderado en 2024, alineado con la recuperación gradual de la actividad económica peruana, cuyo PBI creció aproximadamente 3.1% en dicho año. Para 2025, las proyecciones del Banco Central de Reserva del Perú estiman un crecimiento del PBI en torno a 2.9%, lo que sostendría una demanda estable de combustibles, particularmente diésel y gasolinas, impulsada por los sectores transporte, minería y construcción.\n\nEl entorno regulatorio también incide en el sector. La política de estabilización de precios de combustibles a través del Fondo de Estabilización de Precios (FEPC) sigue vigente, lo que amortigua el traslado de la volatilidad internacional al consumidor final, pero genera pasivos contingentes para el Estado y afecta los márgenes de refinación y comercialización de los operadores del mercado.\n\nEn términos de infraestructura, la modernización de la Refinería de Talara —operada por Petroperú— representa un hito relevante para el subsector, al incrementar la capacidad de procesamiento y mejorar la calidad de los combustibles producidos localmente. No obstante, los sobrecostos y retrasos asociados a este proyecto han tenido un impacto financiero significativo en la empresa estatal.\n\nEn síntesis, el subsector Oil, Gas & Consumable Fuels en Perú opera en un contexto de producción petrolera declinante, alta dependencia importadora, precios internacionales volátiles y un marco regulatorio que busca equilibrar competitividad con protección al consumidor, configurando un escenario exigente para los actores del mercado.",
          "caracteres": 3206
        },
        "producto_demanda_mercado": {
          "contenido": "# PetroPerú – Producto, Demanda y Mercado\n\n**Portafolio de Productos**\n\nPetroPerú opera como la empresa estatal de hidrocarburos del Perú, con un portafolio centrado en la refinación, transporte, comercialización y distribución de combustibles derivados del petróleo. Sus principales productos incluyen gasolinas (84, 90, 95 y 97 octanos), diésel B5 S-50, turbo A-1 para aviación, GLP (gas licuado de petróleo), petróleos industriales, asfaltos y solventes. La compañía comercializa estos productos a través de su red de estaciones de servicio bajo la marca PETROPERÚ, plantas de abastecimiento distribuidas a nivel nacional y ventas directas a clientes industriales, mineros y del sector aviación.\n\n**Capacidad Operativa y Refinación**\n\nLa Refinería de Talara, tras la culminación del Proyecto de Modernización (PMRT), constituye el activo estratégico central de la empresa. Con una capacidad de procesamiento de aproximadamente 95,000 barriles por día, la refinería modernizada permite producir combustibles con menor contenido de azufre, alineados con estándares ambientales más exigentes. Durante 2024, PetroPerú ha enfrentado desafíos operativos significativos para estabilizar las unidades de la nueva refinería y alcanzar niveles óptimos de utilización, lo que ha impactado directamente en sus volúmenes de producción y en la necesidad de complementar oferta mediante importaciones de productos terminados.\n\n**Demanda y Posición de Mercado**\n\nPetroPerú mantiene una participación relevante en el mercado peruano de combustibles líquidos, compitiendo principalmente con Repsol (Refinería La Pampilla) y distribuidores privados. La empresa abastece una porción significativa de la demanda nacional de diésel y gasolinas, con presencia predominante en las regiones del norte, oriente y sur del país, donde su infraestructura logística —incluyendo el Oleoducto Norperuano— le otorga ventaja competitiva frente a competidores privados.\n\nEn 2024 y hacia 2025, la demanda interna de combustibles en Perú se mantiene sostenida por los sectores transporte, minería, pesca e industria. PetroPerú atiende además contratos de suministro de turbo combustible a aeropuertos nacionales y ventas a grandes clientes del sector minero, segmentos que representan fuentes de ingreso de mayor volumen y estabilidad.\n\n**Desafíos Comerciales**\n\nNo obstante su posición estratégica, la empresa enfrenta presiones sobre sus márgenes de refinación, elevado endeudamiento derivado del PMRT y restricciones de liquidez que han condicionado su capacidad de compra de crudo y su competitividad comercial. La estabilización plena de la Refinería de Talara resulta crítica para mejorar el mix de productos, reducir la dependencia de importaciones y recuperar márgenes operativos durante 2025.",
          "caracteres": 2767
        }
      },
      "metadata": {
        "analizado_por": "system",
        "servicio": {
          "model": "claude-opus-4-6",
          "max_tokens": 4000,
          "temperature": 0.3,
        },
        "request_id": "5651e87d-d8f0-4461-8b9f-ceff719c6642"
      },
      "request_id": "5651e87d-d8f0-4461-8b9f-ceff719c6642"
    },
    {
      "business_id": "43e9f078-e9c3-4150-8689-0758ab06512e",
      "analysis": {
        "sector_economico": {
          "contenido": "**Sector Energy – Subsector Oil, Gas & Consumable Fuels en Perú**\n\nEl sector de hidrocarburos en Perú atraviesa un periodo de desafíos estructurales y coyunturales que condicionan el desempeño de las empresas del rubro. La producción nacional de petróleo crudo se mantiene en niveles históricamente bajos, con un promedio cercano a los 40,000 barriles diarios durante 2024, cifra que evidencia la madurez de los campos existentes y la limitada inversión en exploración de nuevos lotes. Esta situación convierte al país en un importador neto de crudo y derivados, lo que expone al sector a la volatilidad de los precios internacionales y al tipo de cambio.\n\nEn cuanto al gas natural, la producción se sostiene principalmente por el proyecto Camisea, que continúa siendo el eje del suministro energético nacional. El gas natural representa una porción creciente de la matriz energética peruana, contribuyendo tanto a la generación eléctrica como al consumo vehicular e industrial. No obstante, la expansión de la red de distribución de gas natural a regiones del sur del país ha enfrentado retrasos que limitan la masificación del recurso.\n\nPara 2025, el Ministerio de Energía y Minas ha proyectado esfuerzos orientados a reactivar la actividad exploratoria mediante la promoción de nuevos contratos de licencia y la simplificación de procesos regulatorios. Sin embargo, el entorno de inversión sigue condicionado por la incertidumbre política, los conflictos sociales en zonas de operación y los extensos plazos para la obtención de permisos ambientales y sociales.\n\nEl subsector de refinación, directamente vinculado a Petroperú, enfrenta un contexto particularmente complejo. La entrada en operación plena de la Nueva Refinería de Talara —con una capacidad de procesamiento de 95,000 barriles por día— representa un hito para el sector, al permitir la producción de combustibles con menor contenido de azufre alineados con estándares ambientales internacionales. No obstante, los sobrecostos acumulados del proyecto y el elevado nivel de endeudamiento de Petroperú han generado presiones financieras significativas que repercuten en la percepción de riesgo del sector estatal de hidrocarburos.\n\nA nivel de precios, el mercado internacional del crudo Brent se ha mantenido en un rango de USD 70 a 85 por barril durante 2024 e inicios de 2025, influenciado por las decisiones de producción de la OPEP+, la desaceleración de la demanda china y las tensiones geopolíticas en Medio Oriente. Este rango de precios impacta directamente en los márgenes de refinación y en el costo de importación de derivados para el mercado peruano.\n\nEn síntesis, el sector Oil, Gas & Consumable Fuels en Perú opera en un entorno de producción petrolera declinante, alta dependencia de importaciones, oportunidades en gas natural aún no plenamente aprovechadas y un marco regulatorio e institucional que requiere mayor estabilidad para atraer inversión privada de largo plazo.",
          "caracteres": 2953
        }
      },
      "metadata": {
        "analizado_por": "system",
        "servicio": {
          "model": "claude-opus-4-6",
          "max_tokens": 4000,
          "temperature": 0.3,
        },
        "request_id": "27b80024-f054-4b70-979d-94dae8367857"
      },
      "request_id": "27b80024-f054-4b70-979d-94dae8367857"
    },
    {
      "business_id": "43e9f078-e9c3-4150-8689-0758ab06512e",
      "analysis": {
        "rentabilidad": {
          "contenido": "# Análisis de Rentabilidad – PetroPeru (RUC: 20100128218)\n\n## 1. Análisis de Rentabilidad Histórica\n\nPetroPeru atraviesa una crisis de rentabilidad severa y sostenida. Todos los indicadores fundamentales se encuentran en territorio profundamente negativo, reflejando una empresa que destruye valor de manera sistemática.\n\n**Márgenes operativos y netos:**\n\n| Indicador | 2023 | 2024 | LTM |\n|---|---|---|---|\n| Margen Bruto | -10.74% | -10.33% | -2.71% |\n| Margen EBITDA | -25.92% | -16.94% | -9.38% |\n| Margen Operativo | -25.92% | -16.94% | -9.38% |\n| Margen Neto | -36.83% | -32.89% | -24.15% |\n\nLa empresa no logra cubrir sus costos de venta con sus ingresos, lo que se evidencia en un **margen bruto negativo persistente**. Esto es particularmente alarmante porque indica que el negocio base —la comercialización y refinación de combustibles— opera a pérdida antes siquiera de considerar gastos administrativos, financieros o de depreciación. No obstante, se observa una tendencia de mejora relativa: el margen bruto pasó de -10.74% en 2023 a -2.71% en el LTM, lo que sugiere cierto ajuste en precios de venta o reducción parcial de costos operativos.\n\n**Retornos sobre activos y patrimonio:**\n\n| Indicador | 2023 | 2024 | LTM |\n|---|---|---|---|\n| ROA | -14.69% | -11.44% | -8.02% |\n| ROE | -91.48% | -46.75% | -39.61% |\n\nEl ROE de -91.48% en 2023 es extraordinariamente destructivo y refleja no solo pérdidas masivas sino también un patrimonio severamente erosionado. La reducción del ROE negativo hacia -39.61% en el LTM no necesariamente indica mejora operativa genuina; puede deberse parcialmente a inyecciones de capital del Estado peruano que amplían la base patrimonial, diluyendo el ratio. El ROA negativo confirma que los activos totales de la empresa generan retornos negativos, independientemente de la estructura de financiamiento.\n\n**Evolución del EBITDA y utilidad neta (en miles de soles):**\n\n- EBITDA: -1,022,288 (2023) → -585,631 (2024) → -319,379 (LTM)\n- Utilidad Neta: -1,452,669 (2023) → -1,136,909 (2024) → -822,507 (LTM)\n\nLa pérdida neta acumulada entre 2023 y 2024 supera los **S/ 2,589 millones**, una cifra que compromete seriamente la viabilidad financiera de la empresa. Si bien el EBITDA muestra una trayectoria de reducción de pérdidas (de -S/ 1,022 millones a -S/ 319 millones en el LTM), la brecha entre EBITDA y utilidad neta revela una carga financiera y no operativa sustancial que amplifica las pérdidas en aproximadamente S/ 500 millones adicionales por período.\n\nEl hecho de que el **margen EBITDA sea idéntico al margen operativo** en todos los períodos indica que la depreciación y amortización son prácticamente nulas o están siendo capitalizadas, lo cual podría señalar subinversión en mantenimiento de activos o una política contable particular.\n\n---\n\n## 2. Comparación Sectorial\n\nEn el contexto del sector **Energy / Oil, Gas & Consumable Fuels**, PetroPeru se posiciona como un caso atípico extremo:\n\n**Benchmarks típicos del sector a nivel regional e internacional:**\n\n| Indicador | Sector promedio (LatAm) | PetroPeru (2024) | Brecha |\n|---|---|---|---|\n| Margen Bruto | 25-35% | -10.33% | ~-38 pp |\n| Margen EBITDA | 15-25% | -16.94% | ~-37 pp |\n| Margen Neto | 5-12% | -32.89% | ~-42 pp |\n| ROA | 5-10% | -11.44% | ~-18 pp |\n| ROE | 12-20% | -46.75% | ~-62 pp |\n\nEmpresas comparables como **Ecopetrol** (Colombia), **YPF** (Argentina) o incluso **EP Petroecuador** operan con márgenes brutos positivos significativos. La diferencia fundamental radica en que estas empresas, aunque también estatales en varios casos, han logrado estructuras de costos más eficientes, mayor integración vertical efectiva y políticas de precios que reflejan condiciones de mercado.\n\n**Deuda Financiera a EBITDA** de -9.58x (2024) y -17.10x (LTM) no puede interpretarse en el sentido convencional del ratio. Normalmente, un ratio de 3-4x se considera elevado en el sector. En el caso de PetroPeru, el signo negativo proviene del EBITDA negativo, lo que significa que la empresa **no tiene capacidad alguna de servir su deuda con flujo operativo**. La deuda financiera es sustancial y creciente en términos relativos al deterioro del EBITDA.\n\nEl **DSCR (Debt Service Coverage Ratio)** de -0.33x a -0.50x confirma que por cada sol de servicio de deuda, la empresa genera entre -33 y -50 centavos de flujo. Un DSCR saludable debería estar por encima de 1.2x-1.5x. PetroPeru está a una distancia abismal de cualquier nivel de cobertura aceptable.\n\n---\n\n## 3. Factores Clave (Drivers de Rentabilidad)\n\nLos principales factores que explican la destrucción de rentabilidad son:\n\n**a) Política de precios subsidiados y regulados:**\nPetroPeru opera bajo restricciones de precios derivadas del Fondo de Estabilización de Precios de Combustibles (FEPC). La empresa absorbe parcialmente la diferencia entre precios internacionales de crudo/productos refinados y los precios de venta al mercado interno, generando márgenes brutos negativos. El Estado compensa parcialmente estas diferencias, pero los reembolsos suelen ser tardíos e insuficientes.\n\n**b) Ineficiencia operativa de la Refinería de Talara:**\nLa modernización de la Refinería de Talara (Proyecto PMRT), cuya inversión superó los US$ 5,000 millones (muy por encima del presupuesto original), debía mejorar la capacidad de procesamiento y la calidad de los productos. Sin embargo, la puesta en marcha ha enfrentado retrasos, sobrecostos y problemas técnicos que impiden alcanzar la eficiencia operativa proyectada. Los costos de producción permanecen elevados respecto a los ingresos generados.\n\n**c) Estructura de costos rígida:**\nComo empresa estatal, PetroPeru enfrenta rigideces laborales, burocráticas y de gobernanza que limitan su capacidad de ajustar costos rápidamente. Los gastos administrativos y de personal no se reducen proporcionalmente cuando caen los ingresos o márgenes.\n\n**d) Carga financiera excesiva:**\nLa diferencia entre EBITDA y utilidad neta (aproximadamente S/ 430-550 millones por período) refleja una carga de intereses y costos financieros derivados del endeudamiento masivo contraído para financiar el PMRT y las operaciones corrientes. La empresa ha emitido bonos internacionales y contraído préstamos bancarios significativos que generan obligaciones de servicio de deuda que no puede cubrir.\n\n**e) Volatilidad del precio del crudo:**\nComo empresa refinadora y comercializadora, PetroPeru está expuesta a la volatilidad de los precios internacionales del petróleo. Cuando los precios del crudo suben, los costos de materia prima se incrementan, pero la capacidad de trasladar estos aumentos al consumidor final está limitada por la regulación.\n\n**f) Flujo de caja operativo deteriorado:**\nEl margen de flujo de caja operativo pasó de +6.09% en 2023 a -28.86% en 2024, una caída de casi 35 puntos porcentuales. Esto indica que la empresa no solo no genera utilidades, sino que su operación consume efectivo de manera acelerada, obligándola a depender de financiamiento externo o aportes del Estado para mantener operaciones.\n\n---\n\n## 4. Tendencias\n\nSe identifican las siguientes tendencias en los datos:\n\n**Tendencia positiva relativa (reducción de pérdidas):**\n- El EBITDA ha mejorado de -S/ 1,022 millones (2023) a -S/ 319 millones (LTM), una reducción del 69% en la magnitud de la pérdida operativa.\n- El margen bruto ha mejorado de -10.74% a -2.71%, acercándose al punto de equilibrio.\n- El margen EBITDA ha mejorado de -25.92% a -9.38%.\n- El ROA ha mejorado de -14.69% a -8.02%.\n\n**Tendencia negativa persistente:**\n- La utilidad neta sigue siendo profundamente negativa (-S/ 822 millones LTM), indicando que la mejora operativa es insuficiente para compensar la carga financiera.\n- Los ratios de cobertura de deuda permanecen en niveles críticos y sin mejora significativa.\n- El flujo de caja operativo se deterioró dramáticamente en 2024.\n- La relación Deuda Financiera Neta a EBITDA se ha deteriorado progresivamente (de -5.0x a -17.0x), reflejando que la deuda crece o se mantiene mientras el EBITDA negativo se reduce en magnitud pero sigue sin generar capacidad de repago.\n\n**Proyección de escenarios:**\n\nSi la tendencia de mejora en márgenes operativos continúa al ritmo observado, PetroPeru podría alcanzar un **EBITDA breakeven** hacia finales de 2025 o inicios de 2026. Sin embargo, alcanzar un EBITDA positivo suficiente para cubrir el servicio de deuda requeriría márgenes EBITDA de al menos +15% a +20%, lo cual implica una mejora de más de 25 puntos porcentuales desde el nivel actual. Este escenario es altamente improbable sin una reestructuración profunda.\n\n---\n\n## 5. Riesgos\n\n**Riesgo de insolvencia y reestructuración de deuda:**\nCon un DSCR negativo y sin capacidad de generar flujo operativo positivo sostenido, PetroPeru enfrenta un riesgo real de incumplimiento de sus obligaciones financieras. Las agencias calificadoras ya han rebajado su calificación a niveles especulativos. Una reestructuración de deuda o un rescate estatal adicional son escenarios probables, con implicaciones fiscales significativas para el Estado peruano.\n\n**Riesgo político y de gobernanza:**\nComo empresa 100% estatal, PetroPeru está sujeta a decisiones políticas que pueden priorizar objetivos sociales (precios bajos de combustibles, empleo) sobre la rentabilidad. La rotación frecuente de directivos y la interferencia política en decisiones operativas han sido factores históricos de ineficiencia.\n\n**Riesgo de mercado (precios del petróleo):**\nUn incremento sostenido en los precios internacionales del crudo sin ajuste correspondiente en precios de venta ampliaría las pérdidas brutas. Conversamente, una caída de precios podría mejorar temporalmente los márgenes pero reduciría ingresos.\n\n**Riesgo operativo de la Refinería de Talara:**\nSi la refinería modernizada no alcanza su capacidad operativa plena y los niveles de eficiencia proyectados, los costos fijos elevados seguirán presionando los márgenes negativamente. Problemas técnicos, paradas no programadas o deficiencias en la calidad de los productos refinados representan riesgos materiales.\n\n**Riesgo de liquidez:**\nEl flujo de caja operativo negativo (-28.86% en 2024) implica que la empresa necesita financiamiento continuo para operar. Si el acceso a mercados de deuda se cierra o el Estado no proporciona aportes de capital oportunos, PetroPeru podría enfrentar una crisis de liquidez que afecte el abastecimiento de combustibles a nivel nacional.\n\n**Riesgo de erosión patrimonial total:**\nCon un ROE de -39.61% (LTM), el patrimonio se consume aceleradamente. Si las pérdidas continúan al ritmo actual, el patrimonio neto podría volverse negativo en los próximos 2-3 años sin aportes de capital adicionales, lo que técnicamente constituiría una situación de quiebra patrimonial.\n\n**Riesgo regulatorio:**\nCambios en la política del FEPC, en la regulación ambiental (exigencias de combustibles más limpios) o en la política energética nacional podrían alterar significativamente la estructura de costos e ingresos de la empresa.\n\n---\n\n## Conclusión\n\nPetroPeru se encuentra en una situación de **destrucción de valor crónica y severa**, con todos los indicadores de rentabilidad en territorio negativo. Si bien existe una tendencia de reducción de pérdidas operativas entre 2023 y el período LTM, la magnitud del deterioro acumulado, la carga financiera insostenible y las limitaciones estructurales de gobernanza hacen que la recuperación hacia niveles de rentabilidad positiva sea un objetivo de mediano a largo plazo que requiere una combinación de reestructuración financiera, mejora operativa de la Refinería de Talara, ajuste en la política de precios y reformas de gobernanza corporativa. Sin intervención decisiva, la empresa representa un pasivo contingente significativo para el Estado peruano y un riesgo sistémico para el abastecimiento energético del país.",
          "caracteres": 11856
        },
        "generacion_caja": {
          "contenido": "# Análisis de Capacidad de Generación de Caja – PetroPerú\n\n## 1. Flujo de Caja Operativo: Calidad y Sostenibilidad\n\nLa situación del flujo de caja operativo de PetroPerú es profundamente preocupante y refleja un deterioro estructural severo. En 2023, el margen de flujo de caja operativo fue apenas positivo en 6.09%, lo que ya representaba una señal de debilidad para una empresa del sector de hidrocarburos, donde los márgenes operativos de caja suelen ser significativamente superiores. Sin embargo, la situación se agravó dramáticamente en 2024, cuando el margen de FCO se desplomó a -28.86%, evidenciando que la operación no solo dejó de generar caja, sino que la consumió de manera masiva. En el último período de doce meses (LTM), el margen se ubica en -8.89%, lo que sugiere una leve moderación del deterioro pero sin revertir la tendencia negativa.\n\nLa calidad del flujo de caja operativo es extremadamente baja. Una empresa petrolera que no logra generar caja positiva desde sus operaciones enfrenta un problema fundamental de modelo de negocio o de gestión operativa. La transición de un FCO positivo en 2023 a uno profundamente negativo en 2024 puede estar vinculada a una combinación de factores: caída en márgenes de refinación, ineficiencias operativas asociadas a la Refinería de Talara, acumulación de inventarios o deterioro en la cobranza. La sostenibilidad del FCO es prácticamente nula en las condiciones actuales, lo que compromete la viabilidad financiera de la empresa sin intervención externa.\n\n## 2. Inversión y Crecimiento: Patrones de Inversión\n\nAunque no se dispone de cifras desagregadas del flujo de caja de inversión (FCI), la comparación entre el FCO implícito y el Free Cashflow permite inferir los patrones de inversión. En 2023, el Free Cashflow fue de S/ 240,016 miles, lo que indica que las inversiones de capital (CAPEX) fueron moderadas o que el FCO fue suficiente para cubrirlas marginalmente. No obstante, en 2024 el Free Cashflow se desplomó a -S/ 997,597 miles, un deterioro de más de S/ 1.2 millones en un solo año.\n\nEste patrón es consistente con una empresa que probablemente continuó realizando inversiones significativas —posiblemente asociadas a la culminación y puesta en marcha de la Refinería de Talara (Proyecto PMRT)— mientras su capacidad operativa de generación de caja colapsaba. En el LTM, el Free Cashflow se sitúa en -S/ 302,624 miles, lo que podría reflejar una reducción en el ritmo de inversiones pero sin resolver el problema de fondo: la operación sigue destruyendo valor. La empresa se encuentra en una posición donde no puede financiar inversiones de mantenimiento ni de crecimiento con recursos propios, dependiendo enteramente de financiamiento externo o aportes del Estado.\n\n## 3. Flujo de Caja Libre: Capacidad de Generar Valor\n\nLa capacidad de PetroPerú para generar valor medida a través del Free Cashflow es negativa y se ha deteriorado significativamente. El ratio de Free Cashflow sobre Deuda Financiera pasó de 4.66% en 2023 (ya insuficiente) a -17.78% en 2024, ubicándose en -5.54% en el LTM. Esto significa que la empresa no solo no genera caja libre para remunerar a sus acreedores o accionistas, sino que necesita endeudarse adicionalmente para cubrir sus déficits operativos y de inversión.\n\nEn términos absolutos, la destrucción de valor en 2024 por casi S/ 1,000 millones en Free Cashflow negativo es alarmante para cualquier estándar. Para una empresa estatal del sector energético, esto implica que cada período que transcurre sin corrección, la posición financiera se deteriora exponencialmente, incrementando la carga de deuda y los costos financieros futuros. La empresa no está en condiciones de generar valor para ningún stakeholder en su estado actual.\n\n## 4. Ciclo de Caja: Eficiencia en Gestión de Capital de Trabajo\n\nEl Ciclo de Conversión de Caja (CCC) muestra una tendencia de deterioro alarmante. En 2023, el CCC era de -24.39 días, lo que indicaba que PetroPerú financiaba su operación con recursos de proveedores (pagaba después de cobrar y vender), una situación típica de empresas con poder de negociación sobre sus proveedores o con plazos de pago extendidos, posiblemente forzados. Para 2024, el CCC se revirtió completamente a +22.36 días, y en el LTM se amplió a +45.71 días.\n\nEste cambio de casi 70 días en el ciclo de caja entre 2023 y el LTM es extraordinariamente significativo. Implica que la empresa pasó de una posición donde los proveedores financiaban la operación a una donde PetroPerú debe financiar aproximadamente 46 días de operación con recursos propios o deuda. Las causas probables incluyen: endurecimiento de condiciones por parte de proveedores (que exigen pagos más rápidos ante el deterioro crediticio de la empresa), acumulación de inventarios por ineficiencias en la cadena de suministro o en la comercialización, y posible deterioro en los plazos de cobro a clientes.\n\nEl capital de trabajo, aunque sigue siendo negativo (lo que normalmente sería preocupante), ha mejorado de -S/ 3,497,242 miles en 2023 a -S/ 1,424,903 miles en el LTM. Sin embargo, esta \"mejora\" debe interpretarse con cautela: puede reflejar reestructuraciones de pasivos de corto a largo plazo más que una mejora genuina en la gestión operativa del capital de trabajo. El capital de trabajo negativo persistente indica que los pasivos corrientes superan ampliamente a los activos corrientes, lo que genera un riesgo permanente de iliquidez.\n\n## 5. Solvencia y Flexibilidad Financiera\n\nLa capacidad de PetroPerú para enfrentar sus compromisos financieros es críticamente deficiente en múltiples dimensiones:\n\n**Liquidez inmediata:** El Cash Ratio es extremadamente bajo en todos los períodos analizados: 0.80% en 2023, 3.96% en 2024 y 1.21% en el LTM. Esto significa que la caja disponible cubre apenas entre el 1% y el 4% de los pasivos corrientes. La caja absoluta, aunque aumentó de S/ 41,147 miles en 2023 a S/ 130,856 miles en 2024, volvió a caer a S/ 33,903 miles en el LTM, un nivel peligrosamente bajo para una empresa de esta magnitud. PetroPerú opera prácticamente sin colchón de liquidez.\n\n**Cobertura de servicio de deuda:** El DSCR basado en FCO es devastadoramente bajo. En 2023 fue de apenas 0.116x, muy por debajo del mínimo aceptable de 1.0x, lo que ya indicaba incapacidad para cubrir el servicio de deuda con flujo operativo. En 2024 y el LTM, el DSCR se volvió negativo (-0.554x y -0.475x respectivamente), lo que significa que no solo no se cubre el servicio de deuda, sino que la operación misma consume caja. La empresa depende completamente de refinanciamientos, nuevas emisiones de deuda o aportes de capital del Estado para honrar sus obligaciones.\n\n**Relación FCO a Deuda:** El ratio FCO/Deuda Financiera pasó de un ya débil 4.66% en 2023 a -17.78% en 2024 y -5.54% en el LTM. Esto implica que, incluso en el mejor escenario reciente (2023), la empresa necesitaría más de 21 años de FCO para repagar su deuda financiera, asumiendo que todo el FCO se destinara a ese fin. Con FCO negativo, el repago es matemáticamente imposible sin reestructuración o capitalización.\n\n**Relación FCO a Pasivos Totales:** El deterioro de 2.89% en 2023 a -13.29% en 2024 y -3.76% en el LTM confirma que la empresa no tiene capacidad alguna de atender sus obligaciones totales con generación propia de caja.\n\nLa flexibilidad financiera de PetroPerú es prácticamente inexistente. La empresa no tiene margen para absorber shocks adicionales —ya sea una caída en precios del petróleo, un incremento en costos de importación de crudo, o un evento operativo adverso— sin recurrir a apoyo estatal directo.\n\n## 6. Tendencias y Proyecciones\n\nLa evolución de los indicadores financieros de PetroPerú dibuja una trayectoria de deterioro acelerado entre 2023 y 2024, con una leve moderación en el LTM que no constituye una reversión de tendencia:\n\n**Tendencia general:** Todos los indicadores clave de generación de caja se deterioraron significativamente entre 2023 y 2024. El Free Cashflow pasó de positivo a profundamente negativo, el DSCR se hundió en territorio negativo, el ciclo de caja se amplió en casi 70 días, y la liquidez inmediata, aunque tuvo un repunte transitorio, volvió a niveles críticos.\n\n**Factores estructurales:** El deterioro parece estar vinculado a problemas estructurales más que coyunturales: la Refinería de Talara, que debía ser el catalizador de mejora operativa, aparentemente no ha logrado generar los retornos esperados en sus primeros años de operación plena. Los costos operativos elevados, posibles ineficiencias en la gestión comercial y una carga de deuda insostenible configuran un círculo vicioso donde el deterioro financiero alimenta mayores costos de financiamiento, que a su vez profundizan el deterioro.\n\n**Proyección a corto plazo:** Sin una intervención decisiva —que podría incluir capitalización por parte del Estado, reestructuración integral de deuda, optimización operativa profunda o una combinación de todas— la empresa enfrenta un riesgo real de insolvencia técnica. Los niveles actuales de caja (S/ 33,903 miles en el LTM) son insuficientes para operar con normalidad, y la dependencia de financiamiento externo es total.\n\n**Escenario base:** En ausencia de reformas estructurales, es razonable proyectar que PetroPerú continuará generando Free Cashflow negativo durante los próximos 12 a 24 meses, con necesidades de financiamiento recurrentes que incrementarán progresivamente su ya elevado nivel de endeudamiento. La mejora relativa observada en el LTM respecto a 2024 podría reflejar ajustes iniciales, pero la magnitud del problema requiere transformaciones de fondo que trascienden ajustes marginales.\n\nEn síntesis, PetroPerú presenta una capacidad de generación de caja severamente comprometida, con indicadores que en su conjunto señalan una empresa en situación de estrés financiero agudo. La combinación de FCO negativo, Free Cashflow negativo, DSCR por debajo de cero, liquidez mínima y un ciclo de caja en rápido deterioro configura un perfil de riesgo crediticio extremadamente elevado, donde la continuidad operativa depende fundamentalmente del respaldo implícito y explícito del Estado peruano como accionista único.",
          "caracteres": 10186
        }
      },
      "metadata": {
        "analizado_por": "system",
        "servicio": {
          "model": "claude-opus-4-6",
          "max_tokens": 4000,
          "temperature": 0.3,
        },
        "request_id": "d312cacb-9260-4a88-b11c-a72c3585c7f2"
      },
      "request_id": "d312cacb-9260-4a88-b11c-a72c3585c7f2"
    },
    {
      "business_id": "43e9f078-e9c3-4150-8689-0758ab06512e",
      "analysis": {
        "solvencia": {
          "contenido": "## Análisis de Solvencia – PetroPeru\n\n**Nivel de Endeudamiento:** PetroPeru presenta un apalancamiento crítico. La deuda financiera sobre activos supera el 56% (2024) y el ratio de solvencia de 132% indica que los pasivos exceden ampliamente el patrimonio, reflejando patrimonio neto negativo. La deuda financiera neta alcanza S/ 5,480 millones.\n\n**Capacidad de Pago:** La situación es alarmante. Los ratios Deuda/EBITDA son negativos (-9.6x en 2024) debido a EBITDA negativo, evidenciando incapacidad operativa para servir deuda. El Cash Ratio de 0.04 y Quick Ratio de 0.21 confirman liquidez extremadamente precaria. El FCO negativo (-17.8% de la deuda) agrava el panorama.\n\n**Riesgo Crediticio:** Muy elevado. La empresa opera con pérdidas operativas crecientes, flujos de caja negativos y dependencia total de respaldo estatal para evitar default. Sin garantía soberana, sería insolvente.\n\n**Comparación Sectorial:** Muy por debajo de pares regionales como Ecopetrol o YPF, que mantienen EBITDA positivo y coberturas saludables. PetroPeru es outlier negativo en el sector.",
          "caracteres": 1076
        },
        "liquidez": {
          "contenido": "## Análisis de Liquidez y Capital de Trabajo – PetroPeru\n\n**Liquidez Corriente:** Los ratios de liquidez (32.0 en 2023, 42.4 en 2024 y 49.2 LTM) aparentan niveles elevados, pero deben interpretarse con cautela dado el capital de trabajo persistentemente negativo, lo que sugiere que los pasivos corrientes superan ampliamente los activos corrientes. Esta aparente contradicción indica una estructura donde activos de largo plazo o inventarios distorsionan el cálculo.\n\n**Liquidez Ácida (Quick Ratio):** Con valores de 0.15 (2023), 0.21 (2024) y 0.24 (LTM), la empresa cubre menos del 25% de sus obligaciones corrientes sin inventarios. El Cash Ratio inferior a 0.04 confirma una posición de caja extremadamente débil, evidenciando dependencia casi total de la conversión de cuentas por cobrar.\n\n**Capital de Trabajo:** Aunque mejora de -3.5 millones (2023) a -1.4 millones (LTM), permanece profundamente negativo. La empresa opera con déficit estructural de recursos corrientes, financiando operaciones con deuda de corto plazo.\n\n**Eficiencia y Rotación:** El flujo de caja libre pasó de positivo (+240K en 2023) a negativo (-998K en 2024), reflejando deterioro operativo severo. La cobertura FCF/Deuda cayó a -17.8%, indicando incapacidad de servir deuda con generación propia.\n\n**Necesidades de Financiación:** PetroPeru enfrenta brechas críticas de financiamiento a corto plazo. La combinación de capital de trabajo negativo, caja mínima y flujo libre negativo configura un escenario de alta vulnerabilidad financiera que requiere inyección de capital o reestructuración de pasivos para garantizar continuidad operativa.",
          "caracteres": 1623
        }
      },
      "metadata": {
        "analizado_por": "system",
        "servicio": {
          "model": "claude-opus-4-6",
          "max_tokens": 4000,
          "temperature": 0.3,

        },
        "request_id": "57003d5e-fe2b-40af-b10c-30bc2186a550"
      },
      "request_id": "57003d5e-fe2b-40af-b10c-30bc2186a550"
    },
    {
      "business_id": "43e9f078-e9c3-4150-8689-0758ab06512e",
      "analysis": {
        "foda": {
          "contenido": "```json\n{\n\"foda\": {\n\"fortalezas\": [\n\"Monopolio estatal en refinación con la Refinería de Talara modernizada con inversión superior a USD 5,000 millones\",\n\"Red de distribución con más de 600 estaciones de servicio bajo su marca a nivel nacional\",\n\"Posición dominante en el abastecimiento de combustibles en zonas remotas y selva peruana\",\n\"Respaldo financiero del Estado peruano como empresa 100% de propiedad estatal\",\n\"Capacidad de refinación ampliada a 95,000 barriles por día tras modernización de Talara\",\n\"Infraestructura logística estratégica con oleoducto norperuano y terminales en costa y selva\"\n],\n\"oportunidades\": [\n\"Demanda creciente de combustibles en Perú impulsada por expansión del parque automotor en 2024-2025\",\n\"Posibilidad de exportar derivados de petróleo de mayor calidad (Euro VI) desde Talara modernizada\",\n\"Potencial de alianzas público-privadas para optimizar operaciones y reducir costos operativos\",\n\"Incremento de producción de crudo en lotes petroleros del noroeste peruano para abastecimiento local\",\n\"Políticas gubernamentales de estabilización de precios de combustibles que aseguran demanda cautiva\"\n],\n\"debilidades\": [\n\"Elevado nivel de endeudamiento con pasivos que superan ampliamente su patrimonio neto, patrimonio negativo\",\n\"Pérdidas operativas recurrentes y flujo de caja negativo que comprometen su sostenibilidad financiera\",\n\"Sobrecostos históricos en el proyecto de modernización de Talara que erosionaron la confianza inversionista\",\n\"Gobernanza corporativa débil con alta rotación de directivos y denuncias de corrupción\",\n\"Dependencia de transferencias y garantías del Tesoro Público para cubrir obligaciones financieras\",\n\"Ineficiencias operativas y exceso de personal comparado con empresas privadas del sector\"\n],\n\"amenazas\": [\n\"Volatilidad del precio internacional del petróleo crudo Brent que impacta directamente los márgenes de refinación\",\n\"Transición energética global y políticas de descarbonización que reducen demanda futura de combustibles fósiles\",\n\"Competencia de importadores privados de combustibles como Repsol, Primax y Valero en el mercado peruano\",\n\"Riesgo de rebaja crediticia soberana de Perú que encarecería el financiamiento de la empresa\",\n\"Conflictos sociales y bloqueos en zonas de operación del oleoducto norperuano que interrumpen el transporte de crudo\",\n\"Presión política y social para privatizar o reestructurar la empresa ante sus persistentes pérdidas\"\n]\n}\n}\n```",
          "caracteres": 2445
        },
        "riesgos": {
          "contenido": "## Análisis de Riesgos – PetroPerú\n\n**Riesgos Financieros:** La situación es crítica. El Cash Ratio inferior a 0.04 evidencia incapacidad para cubrir obligaciones inmediatas con efectivo. La deuda financiera supera el 56% de los activos y los ratios Deuda/EBITDA son negativos y deteriorándose (-5x a -17x), indicando EBITDA negativo persistente. El ratio de solvencia superior a 100% confirma que los pasivos superan los activos, reflejando patrimonio negativo. El flujo de caja operativo se tornó negativo en 2024, eliminando la única fuente de repago orgánico.\n\n**Riesgos Operativos:** La generación operativa negativa sugiere ineficiencias estructurales, probablemente vinculadas a la Refinería de Talara y costos operativos elevados. La dependencia del soporte estatal es total.\n\n**Riesgos de Mercado:** Exposición directa a volatilidad del precio del crudo, tipo de cambio y competencia de importadores privados que operan con mayor eficiencia.\n\n**Riesgos Regulatorios:** Como empresa estatal, enfrenta restricciones de gobernanza, interferencia política en decisiones comerciales y posibles cambios en su marco legal o eventual privatización.\n\n**Factores Externos:** La desaceleración económica peruana, inestabilidad política y la transición energética global representan amenazas estructurales para su viabilidad a mediano plazo. El riesgo de insolvencia es elevado sin respaldo soberano.",
          "caracteres": 1397
        }
      },
      "metadata": {
        "analizado_por": "system",
        "servicio": {
          "model": "claude-opus-4-6",
          "max_tokens": 4000,
          "temperature": 0.3,

        },
        "request_id": "2a16bc75-e367-427e-835c-f7daa1822a5f"
      },
      "request_id": "2a16bc75-e367-427e-835c-f7daa1822a5f"
    }
  ],
  "user_id": "a4b80458-9001-70f2-c029-b4ba12b1c1fd",
  "credit_memo_id": "2f719f37-6153-4a55-b69e-60732bf55081",
  "business_id": "43e9f078-e9c3-4150-8689-0758ab06512e"
}

class Context:
    def __init__(self):
        self.aws_request_id = "test-request-id"
"""
result = lambda_handler(event, Context())
import json
output_path = "debug_payload.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"JSON guardado en {output_path}")
"""