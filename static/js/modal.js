function abrirModal(id, tipo, status, descricao) {

  document.getElementById("tipo").value = tipo
  document.getElementById("status").value = status
  document.getElementById("descricao").value = descricao

  document.getElementById("formEditar").action = "/manutencoes/editar/" + id

  var modal = new bootstrap.Modal(document.getElementById('modalEditar'))
  modal.show()
}