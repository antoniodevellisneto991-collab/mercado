from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Produto, Fornecedor, Entrada, Lote, Ajuste, Venda, ItemVenda, Funcionario
from .services import baixar_estoque_fefo


class VencimentoFilter(admin.SimpleListFilter):
    title = 'vencimento'
    parameter_name = 'vencimento'

    def lookups(self, request, model_admin):
        return [
            ('vencido', 'Já vencido'),
            ('7', 'Próximos 7 dias'),
            ('15', 'Próximos 15 dias'),
            ('30', 'Próximos 30 dias'),
        ]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        hoje = timezone.localdate()
        qs = queryset.filter(validade__isnull=False, quantidade_atual__gt=0)
        if self.value() == 'vencido':
            return qs.filter(validade__lt=hoje)
        dias = int(self.value())
        return qs.filter(validade__gte=hoje, validade__lte=hoje + timedelta(days=dias))


class LoteInline(admin.TabularInline):
    model = Lote
    extra = 1
    fields = ('produto', 'quantidade_inicial', 'custo_unitario', 'validade', 'numero_lote')
    autocomplete_fields = ['produto']


@admin.register(Entrada)
class EntradaAdmin(admin.ModelAdmin):
    inlines = [LoteInline]
    list_display = ('id', 'data', 'fornecedor')
    list_filter = ('fornecedor',)


class EstoqueFilter(admin.SimpleListFilter):
    """Compara a anotação estoque_total (soma dos lotes) com o estoque_minimo do produto.

    Só funciona porque ProdutoAdmin.get_queryset já anotou estoque_total —
    o admin aplica os filtros por cima do queryset que ele devolve.
    """

    title = 'situação do estoque'
    parameter_name = 'estoque'

    def lookups(self, request, model_admin):
        return [
            ('abaixo', 'Abaixo do mínimo'),
            ('zerado', 'Zerado'),
            ('ok', 'No mínimo ou acima'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'abaixo':
            return queryset.filter(estoque_total__lt=F('estoque_minimo'))
        if self.value() == 'zerado':
            return queryset.filter(estoque_total=0)
        if self.value() == 'ok':
            return queryset.filter(estoque_total__gte=F('estoque_minimo'))
        return queryset


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'preco_venda', 'estoque_total', 'estoque_minimo')
    search_fields = ('nome', 'ean')
    list_filter = (EstoqueFilter, 'categoria', 'unidade', 'ativo', 'perecivel')

    def get_queryset(self, request):
        # Sum devolve NULL para produto sem lote nenhum; Coalesce troca por 0
        # para que a comparação com estoque_minimo funcione em todos os casos.
        return super().get_queryset(request).annotate(
            estoque_total=Coalesce(
                Sum('lotes__quantidade_atual'),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            )
        )

    @admin.display(description='estoque total', ordering='estoque_total')
    def estoque_total(self, obj):
        return obj.estoque_total


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ('produto', 'quantidade_atual', 'validade', 'entrada')
    search_fields = ('produto__nome',)
    list_filter = (VencimentoFilter, 'produto__categoria', 'produto__perecivel')

    def has_add_permission(self, request):
        return False


class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 1
    fields = ('produto', 'quantidade', 'preco_unitario', 'cobertura')
    readonly_fields = ('cobertura',)
    autocomplete_fields = ['produto']

    @admin.display(description='cobertura de estoque')
    def cobertura(self, obj):
        """Traduz quantidade_sem_lote para gente: 0 = disponível; >0 = alerta."""
        if obj.pk is None:
            return '—'
        if obj.quantidade_sem_lote == 0:
            return 'disponível'
        return format_html(
            '<b style="color:#ba2121">faltou {} sem lote</b>',
            obj.quantidade_sem_lote.normalize(),
        )


@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    """Caixa improvisado até a tela de venda existir.

    Venda é imutável: criada, não se edita nem se apaga (a baixa nos lotes
    já aconteceu; desfazer exigiria estorno, que fica para depois via Ajuste).
    """

    inlines = [ItemVendaInline]
    list_display = ('id', 'data_hora', 'forma_pagamento', 'total_venda')
    list_filter = ('forma_pagamento',)
    date_hierarchy = 'data_hora'

    def has_change_permission(self, request, obj=None):
        return False  # ainda dá para VER (view permission), só não editar

    def has_delete_permission(self, request, obj=None):
        return False

    def save_related(self, request, form, formsets, change):
        """Depois que os itens do inline são salvos, dispara a baixa FEFO.

        Só roda na criação (change nunca acontece: has_change_permission=False).
        O admin já envolve tudo numa transação — venda e baixa são atômicas.
        """
        super().save_related(request, form, formsets, change)
        for item in form.instance.itens.all():
            baixar_estoque_fefo(item)

    @admin.display(description='total')
    def total_venda(self, obj):
        return obj.total


@admin.register(Ajuste)
class AjusteAdmin(admin.ModelAdmin):
    """Livro-razão: ajustes só entram, nunca mudam nem saem."""

    list_display = ('id', 'data', 'lote', 'motivo', 'quantidade')
    list_filter = ('motivo',)
    autocomplete_fields = ['lote']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Fornecedor)


class FuncionarioInline(admin.StackedInline):
    """O nível de acesso aparece dentro da própria tela de usuário —
    criar um login e dar o nível é uma operação só."""

    model = Funcionario
    can_delete = False
    verbose_name_plural = 'nível de acesso no sistema'


admin.site.unregister(User)


@admin.register(User)
class UserComNivelAdmin(UserAdmin):
    inlines = [FuncionarioInline]
    list_display = ('username', 'first_name', 'nivel', 'is_active')

    @admin.display(description='nível')
    def nivel(self, obj):
        f = getattr(obj, 'funcionario', None)
        if f:
            return f.get_nivel_display()
        return 'Gerente (dono)' if obj.is_superuser else '—'
