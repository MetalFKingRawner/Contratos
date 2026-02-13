from django.db import models
from django.conf import settings
from financiamiento.models import Financiamiento
from core.models import Cliente, Vendedor, Propietario
from django.contrib.auth.models import User

class Tramite(models.Model):
    financiamiento = models.ForeignKey(Financiamiento, on_delete=models.PROTECT)
    financiamiento_commeta = models.ForeignKey(
        'financiamiento.FinanciamientoCommeta',  # Referencia al modelo
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tramites_commeta',
        verbose_name="Financiamiento Commeta (si aplica)"
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    
    # Campos para la persona que atendió (puede ser vendedor o propietario)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.PROTECT, null=True, blank=True)
    propietario = models.ForeignKey(Propietario, on_delete=models.PROTECT, null=True, blank=True)
    
    # Nuevo campo para registrar el usuario de Django que creó el trámite
    usuario_creador = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        verbose_name="Usuario que creó el trámite",
        related_name="tramites_creados"
    )

    # Campos para identificar el tipo de persona seleccionada
    persona_tipo = models.CharField(
        max_length=20, 
        choices=[('vendedor', 'Vendedor'), ('propietario', 'Propietario')],
        null=True,  # Temporalmente nullable
        blank=True  # Temporalmente blank
    )
    persona_id = models.PositiveIntegerField(
        null=True,  # Temporalmente nullable
        blank=True  # Temporalmente blank
    )

    # Firma del vendedor (en aviso de privacidad)
    firma_vendedor = models.TextField(
        blank=True, help_text="Data‑URL base64 de la firma del vendedor"
    )
    
    firma_cliente = models.TextField(
        blank=True, help_text="Data‑URL base64 de la firma del cliente"
    )
    link_firma_cliente = models.CharField(max_length=255, blank=True, help_text="Link único para firma del cliente")
    cliente_2 = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name='tramites_as_second')
    firma_cliente2 = models.TextField(
        blank=True, help_text="Data‑URL base64 de la firma del segundo cliente"
    )
    link_firma_cliente2 = models.CharField(max_length=255, blank=True, help_text="Link único para firma del segundo cliente")

    # Testigos (máximo 2, uno de ellos es el vendedor)
    testigo_1_nombre = models.CharField(max_length=150, blank=True, help_text="Nombre del testigo 1")
    testigo_1_firma = models.TextField(blank=True, help_text="Firma del testigo 1")
    
    testigo_2_nombre = models.CharField(max_length=150, blank=True, help_text="Nombre del testigo 2")
    testigo_2_firma = models.TextField(blank=True, help_text="Firma del testigo 2")
    link_firma_testigo1 = models.CharField(max_length=255, blank=True, help_text="Link único para firma de testigo")
    link_firma_testigo2 = models.CharField(max_length=255, blank=True, help_text="Link único para firma del segundo testigo")
    
    # Beneficiarios (máximo 2)
    # BENEFICIARIOS - CAMBIO: ahora son ForeignKey
    beneficiario_1 = models.ForeignKey(
        'core.Beneficiario', 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='tramites_beneficiario1',
        verbose_name="Beneficiario 1"
    )
    beneficiario_2 = models.ForeignKey(
        'core.Beneficiario', 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='tramites_beneficiario2',
        verbose_name="Beneficiario 2"
    )
    # MANTENEMOS estos campos para las firmas (no cambian)
    beneficiario_1_firma = models.TextField(blank=True, help_text="Firma del beneficiario 1")
    beneficiario_2_firma = models.TextField(blank=True, help_text="Firma del beneficiario 2")
    link_firma_beneficiario1 = models.CharField(max_length=255, blank=True)
    link_firma_beneficiario2 = models.CharField(max_length=255, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Trámite #{self.pk} – {self.cliente.nombre_completo}"

    # En la misma clase Tramite, agregar estas propiedades:

    @property
    def es_commeta(self):
        """Devuelve True si el trámite usa financiamiento Commeta"""
        return self.financiamiento_commeta is not None

    @property
    def obtener_detalle_commeta(self):
        """Devuelve el detalle Commeta si existe, de forma segura"""
        if self.es_commeta:
            return self.financiamiento_commeta
        # Fallback: intentar obtenerlo desde financiamiento base
        return getattr(self.financiamiento, 'detalle_commeta', None)

    @property
    def obtener_configuracion_commeta(self):
        """Obtiene la configuración Commeta si existe"""
        if self.es_commeta and hasattr(self.financiamiento_commeta, 'configuracion_original'):
            return self.financiamiento_commeta.configuracion_original
        return None

    @property
    def zona_commeta(self):
        """Devuelve la zona Commeta si aplica"""
        config = self.obtener_configuracion_commeta
        if config:
            return config.get_zona_display()
        return None

    @property
    def tipo_esquema_commeta(self):
        """Devuelve el tipo de esquema Commeta si aplica"""
        if self.es_commeta:
            return self.financiamiento_commeta.get_tipo_esquema_display()
        return None
    
    @property
    def persona(self):
        """Método para obtener la persona (vendedor o propietario) de forma uniforme"""
        if self.persona_tipo == 'vendedor' and self.vendedor:
            return self.vendedor
        elif self.persona_tipo == 'propietario' and self.propietario:
            return self.propietario
        return None
    
    def save(self, *args, **kwargs):
        # Asegurarnos de que persona_id y persona_tipo sean consistentes
        if self.vendedor:
            self.persona_tipo = 'vendedor'
            self.persona_id = self.vendedor.id
        elif self.propietario:
            self.persona_tipo = 'propietario'
            self.persona_id = self.propietario.id
        
        super().save(*args, **kwargs)

    def generar_links_firma(self):
        """Genera links únicos SOLO para las firmas de involucrados existentes"""
        import secrets
        
        # Helper function para generar tokens
        def generar_token():
            return secrets.token_urlsafe(32)
        
        links_generados = []  # Para tracking de qué links se crearon
        
        # 1. CLIENTE PRINCIPAL - SIEMPRE existe
        if not self.link_firma_cliente:
            self.link_firma_cliente = generar_token()
            links_generados.append('cliente_principal')
            print(f"✅ Link generado para cliente principal: {self.link_firma_cliente[:20]}...")
        
        # 2. SEGUNDO CLIENTE - solo si existe
        if self.cliente_2 and not self.link_firma_cliente2:
            self.link_firma_cliente2 = generar_token()
            links_generados.append('segundo_cliente')
            print(f"✅ Link generado para segundo cliente: {self.link_firma_cliente2[:20]}...")
        
        # 3. BENEFICIARIO - solo si existe (usamos beneficiario_1 ya que es el único)
        if self.beneficiario_1 and not self.link_firma_beneficiario1:
            self.link_firma_beneficiario1 = generar_token()
            links_generados.append('beneficiario')
            print(f"✅ Link generado para beneficiario: {self.link_firma_beneficiario1[:20]}...")
        
        # 4. TESTIGO 1 - solo si existe nombre (el testigo 1 es el vendedor/propietario)
        if self.testigo_1_nombre and not self.link_firma_testigo1:
            self.link_firma_testigo1 = generar_token()
            links_generados.append('testigo_1')
            print(f"✅ Link generado para testigo 1: {self.link_firma_testigo1[:20]}...")
        
        # 5. TESTIGO 2 - solo si existe nombre
        if self.testigo_2_nombre and not self.link_firma_testigo2:
            self.link_firma_testigo2 = generar_token()
            links_generados.append('testigo_2')
            print(f"✅ Link generado para testigo 2: {self.link_firma_testigo2[:20]}...")
        
        # NOTA: Eliminamos la generación para beneficiario_2 ya que ahora solo tenemos uno
        
        if links_generados:
            self.save()
            print(f"🎯 Links generados para: {', '.join(links_generados)}")
        else:
            print("ℹ️  No se generaron nuevos links - todos los necesarios ya existían")
        
        return links_generados

    # También agregamos un método para obtener los links activos
    @property
    def links_activos(self):
        """Retorna un diccionario con todos los links que están activos (existen y tienen token)"""
        activos = {}
        
        # Cliente principal - siempre activo
        if self.link_firma_cliente:
            activos['cliente'] = self.link_firma_cliente
        
        # Segundo cliente - solo si existe y tiene token
        if self.cliente_2 and self.link_firma_cliente2:
            activos['segundo_cliente'] = self.link_firma_cliente2
        
        # Beneficiario - solo si existe y tiene token
        if self.beneficiario_1 and self.link_firma_beneficiario1:
            activos['beneficiario'] = self.link_firma_beneficiario1
        
        # Testigos - solo si existen y tienen token
        if self.testigo_1_nombre and self.link_firma_testigo1:
            activos['testigo_1'] = self.link_firma_testigo1
        
        if self.testigo_2_nombre and self.link_firma_testigo2:
            activos['testigo_2'] = self.link_firma_testigo2
        
        return activos

    # Método para obtener URLs completas (útil para el template)
    def obtener_urls_firma(self, request):
        """Retorna las URLs completas para cada tipo de firmante"""
        from django.urls import reverse
        
        urls = {}
        activos = self.links_activos
        
        base_url = f"{request.scheme}://{request.get_host()}"
        
        if 'cliente' in activos:
            urls['cliente'] = f"{base_url}{reverse('firma_cliente', args=[activos['cliente']])}"
        
        if 'segundo_cliente' in activos:
            urls['segundo_cliente'] = f"{base_url}{reverse('firma_segundo_cliente', args=[activos['segundo_cliente']])}"
        
        if 'beneficiario' in activos:
            urls['beneficiario'] = f"{base_url}{reverse('firma_beneficiario', args=[activos['beneficiario']])}"
        
        if 'testigo_1' in activos:
            urls['testigo_1'] = f"{base_url}{reverse('firma_testigo1', args=[activos['testigo_1']])}"
        
        if 'testigo_2' in activos:
            urls['testigo_2'] = f"{base_url}{reverse('firma_testigo2', args=[activos['testigo_2']])}"
        
        return urls

    @property
    def estado_firmas(self):
        """Retorna el estado general de las firmas"""
        firmas_completadas = 0
        firmas_totales = 0
        
        # Cliente principal siempre cuenta
        firmas_totales += 1
        if self.firma_cliente:
            firmas_completadas += 1
        
        # Segundo cliente si existe
        if self.cliente_2:
            firmas_totales += 1
            if self.firma_cliente2:
                firmas_completadas += 1
        
        # Beneficiario si existe
        if self.beneficiario_1:
            firmas_totales += 1
            if self.beneficiario_1_firma:
                firmas_completadas += 1
        
        # Testigos si existen
        if self.testigo_1_nombre:
            firmas_totales += 1
            if self.testigo_1_firma:
                firmas_completadas += 1
        
        if self.testigo_2_nombre:
            firmas_totales += 1
            if self.testigo_2_firma:
                firmas_completadas += 1
        
        if firmas_totales == 0:
            return "sin_firmas"
        
        porcentaje = (firmas_completadas / firmas_totales) * 100
        
        if porcentaje == 100:
            return "completado"
        elif porcentaje > 0:
            return "en_proceso"
        else:
            return "pendiente"

    @property
    def porcentaje_firmas(self):
        """Calcula el porcentaje de firmas completadas"""
        firmas_completadas = 0
        firmas_totales = 0
        
        # Misma lógica que arriba
        if self.firma_cliente: firmas_completadas += 1
        firmas_totales += 1
        
        if self.cliente_2:
            firmas_totales += 1
            if self.firma_cliente2: firmas_completadas += 1
        
        if self.beneficiario_1:
            firmas_totales += 1
            if self.beneficiario_1_firma: firmas_completadas += 1
        
        if self.testigo_1_nombre:
            firmas_totales += 1
            if self.testigo_1_firma: firmas_completadas += 1
        
        if self.testigo_2_nombre:
            firmas_totales += 1
            if self.testigo_2_firma: firmas_completadas += 1
        
        return int((firmas_completadas / firmas_totales) * 100) if firmas_totales > 0 else 0

    @property
    def firmas_pendientes(self):
        """Lista de firmas pendientes"""
        pendientes = []
        if not self.firma_cliente:
            pendientes.append("Cliente Principal")
        if self.cliente_2 and not self.firma_cliente2:
            pendientes.append("Segundo Cliente")
        if self.beneficiario_1 and not self.beneficiario_1_firma:
            pendientes.append("Beneficiario")
        if self.testigo_1_nombre and not self.testigo_1_firma:
            pendientes.append("Testigo 1")
        if self.testigo_2_nombre and not self.testigo_2_firma:
            pendientes.append("Testigo 2")
        return pendientes

    @property
    def tiene_firmas_pendientes(self):
        """Verifica si hay firmas pendientes"""
        return len(self.firmas_pendientes) > 0

    @property
    def saldo_a_favor_disponible(self):
        """Retorna el saldo a favor total disponible"""
        from pagos.models import SaldoAFavor
        saldos = SaldoAFavor.objects.filter(tramite=self, utilizado=False)
        total = saldos.aggregate(total=models.Sum('monto'))['total']
        return total if total else 0
    
    def obtener_urls_firma_completas(self, request):
        """Retorna las URLs completas para cada tipo de firmante usando las URLs de workflow"""
        from django.urls import reverse
        from django.urls.exceptions import NoReverseMatch
        
        urls = {}
        activos = self.links_activos
        
        base_url = f"{request.scheme}://{request.get_host()}"
        
        # Mapeo de tipos internos a nombres de URL de workflow
        url_map = {
            'cliente': 'workflow:firma_cliente',
            'segundo_cliente': 'workflow:firma_segundo_cliente',
            'beneficiario': 'workflow:firma_beneficiario',
            'testigo_1': 'workflow:firma_testigo1', 
            'testigo_2': 'workflow:firma_testigo2',
        }
        
        for tipo, token in activos.items():
            if tipo in url_map:
                try:
                    url_name = url_map[tipo]
                    urls[tipo] = f"{base_url}{reverse(url_name, args=[token])}"
                except NoReverseMatch:
                    print(f"⚠️ URL no encontrada para: {url_name}")
                    continue
        
        return urls

# workflow/models.py
class ClausulasEspeciales(models.Model):
    tramite = models.OneToOneField(
        'Tramite', 
        on_delete=models.CASCADE, 
        related_name='clausulas_especiales'
    )
    clausula_pago = models.TextField(
        blank=True, 
        verbose_name="Cláusula de Pago Personalizada"
    )
    clausula_deslinde = models.TextField(
        blank=True, 
        verbose_name="Cláusula de Deslinde Personalizada"
    )
    clausula_promesa = models.TextField(
        blank=True, 
        verbose_name="Cláusula de Promesa Personalizada"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cláusulas Especiales del Trámite"
        verbose_name_plural = "Cláusulas Especiales de los Trámites"

    def __str__(self):
        return f"Cláusulas especiales - Trámite #{self.tramite.id}"

