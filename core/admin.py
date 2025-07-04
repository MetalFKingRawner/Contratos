from django.contrib import admin
from .models import Cliente, Proyecto, Lote, Propietario, Vendedor

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display  = ('nombre_completo','rfc','telefono','email')
    search_fields = ('nombre_completo','rfc')

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display  = ('nombre','tipo_contrato')
    search_fields = ('nombre','tipo_contrato')

@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display  = ('identificador', 'get_proyecto')
    search_fields = ('identificador', 'proyecto__nombre')

    def get_proyecto(self, obj):
        return obj.proyecto.nombre
    get_proyecto.short_description = 'Proyecto'
    get_proyecto.admin_order_field = 'proyecto__nombre'

@admin.register(Propietario)
class PropietarioAdmin(admin.ModelAdmin):
    list_display  = ('nombre_completo','telefono','email','tipo','get_lotes')
    search_fields = ('tipo', 'notario_publico')

    def get_lotes(self, obj):
        # obj.proyecto es el Proyecto asociado (OneToOne)
        lotes = obj.proyecto.lotes.all()
        return ", ".join(l.identificador for l in lotes) or '-'
    get_lotes.short_description = 'Lotes vinculados'

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display  = ('nombre_completo','telefono','email','tipo','get_lotes')
    search_fields = ('tipo','email','nombre_completo')

    def get_lotes(self, obj):
        # Recorremos todos los proyectos del vendedor
        lotes = Lote.objects.filter(proyecto__in=obj.proyectos.all())
        # Evitamos duplicados y extraemos identificadores
        ids = sorted({l.identificador for l in lotes})
        return ", ".join(ids) or '-'
    get_lotes.short_description = 'Lotes vinculados'
