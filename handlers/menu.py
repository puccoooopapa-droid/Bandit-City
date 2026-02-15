from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_kb

router = Router()

@router.message(F.text == "🏠 Главное меню")
async def main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Вы в главном меню", reply_markup=main_menu_kb())

@router.message(F.text == "⬅️ Назад")
async def back_handler(message: types.Message, state: FSMContext):
    # Универсальный обработчик "Назад", если не перехвачен в конкретном стейте
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("🏠 Главное меню", reply_markup=main_menu_kb())
    else:
        # Если мы в каком-то состоянии, но хендлер состояния не обработал "Назад" (или мы вышли из стейта)
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=main_menu_kb())
